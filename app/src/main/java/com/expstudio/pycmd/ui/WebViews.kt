package com.expstudio.pycmd.ui

import android.annotation.SuppressLint
import android.content.Context
import android.view.ViewGroup
import android.webkit.JavascriptInterface
import android.webkit.ConsoleMessage
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.graphics.toColorInt
import com.expstudio.pycmd.util.DebugLog
import org.json.JSONObject

private const val ASSET_BASE = "file:///android_asset/web/"

/** Must match --bg in console.css and editor.css, or the page flashes on load. */
private const val WEB_BACKGROUND = "#0B0F14"

/**
 * Callbacks the JS layer can reach.
 *
 * The lambdas are held in mutable fields rather than captured at construction:
 * the WebView outlives any single composition, so the bridge has to be able to
 * point at whatever the current composable wants.
 */
class PyBridge {
    var editorChangedHandler: (String) -> Unit = {}
    var cursorMovedHandler: (Int, Int) -> Unit = { _, _ -> }
    var editorReadyHandler: () -> Unit = {}

    // Every method below runs on the WebView's JS thread, never the main
    // thread, so the handlers must not touch views directly.
    @JavascriptInterface
    fun onEditorChanged(text: String) = editorChangedHandler(text)

    @JavascriptInterface
    fun onCursorMoved(line: Int, column: Int) = cursorMovedHandler(line, column)

    @JavascriptInterface
    fun onEditorReady() = editorReadyHandler()
}

/** A WebView plus the bridge wired into it. */
class WebHost(val webView: WebView, val bridge: PyBridge) {

    private var loaded = false

    /**
     * Whether the document is far enough along to take a script.
     *
     * Evaluating JS against a WebView that has not started a document throws
     * it away silently, which is how the theme used to arrive on the console
     * only after the first tab switch.
     */
    private var pageReady = false

    /** The last palette pushed in, re-pushed after every navigation. */
    private var themeScript = ""

    /**
     * Which document the page currently holds.
     *
     * Lives on the host, not in a composable's `remember`: the WebView outlives
     * the composition, and re-pushing the same document on every tab switch
     * would throw the caret back to the top of the file.
     */
    var loadedEpoch: Long = -1L

    fun load(page: String) {
        if (loaded) return
        loaded = true
        webView.loadUrl(ASSET_BASE + page)
    }

    /** Called by the WebViewClient; not for callers outside this file. */
    internal fun onDocumentStarted() {
        pageReady = true
        if (themeScript.isNotEmpty()) eval(themeScript)
    }

    /**
     * Hands the page the current palette.
     *
     * Kept rather than fired and forgotten: a WebView reloads itself when the
     * process is trimmed, and a page that came back in Classic Green while the
     * chrome around it was orange was the first thing anybody noticed about
     * themes.
     */
    fun applyTheme(script: String, background: Int) {
        runCatching { webView.setBackgroundColor(background) }
        if (script == themeScript) return
        themeScript = script
        if (pageReady) eval(script)
    }

    /** Fire-and-forget JS; results are never needed and errors are logged by the WebView. */
    fun eval(script: String) {
        webView.post { webView.evaluateJavascript(script, null) }
    }
}

@SuppressLint("SetJavaScriptEnabled")
private fun createWebView(
    context: Context,
    bridge: PyBridge,
    onDocumentStarted: () -> Unit,
): WebView =
    WebView(context).apply {
        // Without this the view is added with wrap-content and lays the page
        // out in a strip a couple of hundred pixels tall: the page's `height:
        // 100%` then resolves against that, and the console scrolls almost all
        // of its output off the top of a viewport that is barely one line high.
        layoutParams = ViewGroup.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT,
        )
        setBackgroundColor(WEB_BACKGROUND.toColorInt())
        // No remote content is ever loaded, so the usual JS caveats do not
        // apply: every page is an asset shipped inside the APK.
        settings.javaScriptEnabled = true
        settings.domStorageEnabled = true
        // Assets live behind file:///android_asset, so file access stays on;
        // cross-origin reads from a file URL remain disabled by default.
        settings.allowFileAccess = true
        settings.allowContentAccess = false
        settings.cacheMode = android.webkit.WebSettings.LOAD_NO_CACHE
        settings.textZoom = 100
        isVerticalScrollBarEnabled = true
        isHorizontalScrollBarEnabled = false
        overScrollMode = WebView.OVER_SCROLL_NEVER
        addJavascriptInterface(bridge, "PyBridge")

        // Anything the page logs or throws lands in the debug console, which is
        // the only way a JavaScript error in a WebView is ever visible on a
        // phone.
        webChromeClient = object : WebChromeClient() {
            override fun onConsoleMessage(message: ConsoleMessage): Boolean {
                val where = "${message.sourceId().substringAfterLast('/')}:${message.lineNumber()}"
                val text = "${message.message()}  ($where)"
                when (message.messageLevel()) {
                    ConsoleMessage.MessageLevel.ERROR -> DebugLog.error("webview", text)
                    ConsoleMessage.MessageLevel.WARNING -> DebugLog.warn("webview", text)
                    else -> DebugLog.debug("webview", text)
                }
                return true
            }
        }

        webViewClient = object : WebViewClient() {
            // The palette goes in at both ends of the load. At `started` the
            // document exists but has no stylesheet yet, so the colours are
            // already right for the first frame the page paints; at `finished`
            // again, because a page that redrew its own head would otherwise
            // have dropped the block.
            override fun onPageStarted(view: WebView, url: String?, favicon: android.graphics.Bitmap?) {
                onDocumentStarted()
            }

            override fun onPageFinished(view: WebView, url: String?) {
                onDocumentStarted()
            }

            override fun onReceivedError(
                view: WebView,
                request: WebResourceRequest,
                error: WebResourceError,
            ) {
                DebugLog.error(
                    "webview",
                    "failed to load ${request.url}",
                    "${error.errorCode}: ${error.description}",
                )
            }
        }
    }

@Composable
fun rememberWebHost(page: String): WebHost {
    val context = LocalContext.current
    val host = remember(page) {
        val bridge = PyBridge()
        // A one-slot holder because the view and the host each need the other:
        // the client has to call back into the host, and the host is built
        // around the view.
        val slot = arrayOfNulls<WebHost>(1)
        // The activity context is what the soft keyboard and text-selection
        // handles need; the host dies with the composition, so it cannot leak
        // past the activity.
        val view = createWebView(context, bridge) { slot[0]?.onDocumentStarted() }
        WebHost(view, bridge).also {
            slot[0] = it
            it.load(page)
        }
    }
    ThemeWebView(host)
    return host
}

/**
 * Keeps a page's colours in step with the app's.
 *
 * Its own composable rather than a line inside [rememberWebHost] so that the
 * plugin panels, which build their WebViews elsewhere, can use the same path.
 */
@Composable
fun ThemeWebView(host: WebHost) {
    val theme = LocalPyTheme.current
    val corner = LocalCorner.current
    val motion = LocalReducedMotion.current
    val scale = LocalTextScale.current
    androidx.compose.runtime.LaunchedEffect(theme.id, theme.palette, corner, motion, scale) {
        host.applyTheme(
            WebTheme.script(theme, scale, corner, motion),
            Hex.argb(theme.palette.bg).toInt(),
        )
    }
}

/**
 * Renders a hoisted WebView.
 *
 * The instance is created once and survives tab switches, so console history
 * and editor scroll position are not thrown away every time the user looks at
 * something else. Detaching from the previous parent is what makes reuse legal.
 */
@Composable
fun PersistentWebView(host: WebHost, modifier: Modifier = Modifier) {
    AndroidView(
        factory = {
            (host.webView.parent as? ViewGroup)?.removeView(host.webView)
            host.webView
        },
        modifier = modifier,
    )
}

/** Quotes a Kotlin string for safe interpolation into a JS expression. */
fun jsString(value: String): String = JSONObject.quote(value)
