package com.expstudio.pycmd.ui

import android.annotation.SuppressLint
import android.net.Uri
import android.view.ViewGroup
import android.webkit.ConsoleMessage
import android.webkit.JavascriptInterface
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import com.expstudio.pycmd.util.DebugLog

/**
 * Notes: the board (assets/web/board.html), the same page the PC shows in its
 * Notes tab. It reaches the engine through `PyBoardNative.call`, which goes to
 * pycmd_board in the workspace.
 *
 * A screen of its own, full size, rather than a plugin panel: the board pans
 * and pinches, so it has to own every gesture on it, and nothing scrolls
 * around it to take them away.
 */
@SuppressLint("SetJavaScriptEnabled")
@Composable
fun NotesScreen(onCall: (String, String) -> String, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val theme = LocalPyTheme.current
    val corner = LocalCorner.current
    val reducedMotion = LocalReducedMotion.current
    val textScale = LocalTextScale.current
    val holder = remember { NotesHolder() }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
        holder.pending?.onReceiveValue(if (uri != null) arrayOf(uri) else emptyArray())
        holder.pending = null
    }
    holder.pick = { picker.launch("image/*") }
    holder.onCall = onCall

    val webView = remember {
        WebView(context).apply {
            layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
            setBackgroundColor(Hex.argb(theme.palette.bg).toInt())
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.allowFileAccess = true
            settings.allowContentAccess = true
            settings.textZoom = 100
            overScrollMode = WebView.OVER_SCROLL_NEVER
            addJavascriptInterface(BoardBridge(holder), "PyBoardNative")
            webChromeClient = object : WebChromeClient() {
                override fun onShowFileChooser(
                    view: WebView,
                    callback: ValueCallback<Array<Uri>>,
                    params: FileChooserParams,
                ): Boolean {
                    holder.pending?.onReceiveValue(null)
                    holder.pending = callback
                    holder.pick()
                    return true
                }

                override fun onConsoleMessage(message: ConsoleMessage): Boolean {
                    val text = "${message.message()}  (board.html:${message.lineNumber()})"
                    if (message.messageLevel() == ConsoleMessage.MessageLevel.ERROR) DebugLog.error("notes", text)
                    else DebugLog.debug("notes", text)
                    return true
                }
            }
            webViewClient = object : WebViewClient() {
                override fun onPageFinished(view: WebView, url: String?) {
                    holder.theme?.let { view.evaluateJavascript(it, null) }
                }
            }
            loadUrl("file:///android_asset/web/board.html")
        }
    }

    LaunchedEffect(theme.id, theme.palette, corner, reducedMotion, textScale) {
        val script = WebTheme.script(theme, textScale, corner, reducedMotion)
        holder.theme = script
        webView.setBackgroundColor(Hex.argb(theme.palette.bg).toInt())
        webView.evaluateJavascript(script, null)
    }

    AndroidView(factory = { webView }, modifier = modifier.fillMaxSize())
}

/** What the WebView's callbacks need from the latest composition. */
private class NotesHolder {
    @Volatile var onCall: (String, String) -> String = { _, _ -> "{\"ok\":false}" }
    var pending: ValueCallback<Array<Uri>>? = null
    var pick: () -> Unit = {}
    var theme: String? = null
}

private class BoardBridge(private val holder: NotesHolder) {
    @JavascriptInterface
    fun call(name: String, json: String): String = holder.onCall(name, json)
}
