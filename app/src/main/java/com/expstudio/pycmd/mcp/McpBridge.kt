package com.expstudio.pycmd.mcp

import android.os.Handler
import android.os.Looper
import org.json.JSONObject
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * Where the MCP server's ui_* tools reach the screen.
 *
 * pycmd_mcp_android.py runs on a server thread and calls [call] through
 * Chaquopy; the work is posted to the main thread, because only it may touch
 * views, and the server thread waits for the answer. [handler] is set by the
 * app while it is on screen and cleared when it is not.
 */
object McpBridge {

    @Volatile
    var handler: ((String, JSONObject) -> JSONObject)? = null

    private val main = Handler(Looper.getMainLooper())

    @JvmStatic
    fun call(action: String, args: String): String {
        val act = handler ?: return failure("PyCmd is not on screen - open the app on the phone")
        var reply = JSONObject().put("ok", false).put("error", "the app did not answer in time")
        val done = CountDownLatch(1)
        main.post {
            reply = runCatching { act(action, JSONObject(args.ifBlank { "{}" })) }
                .getOrElse { JSONObject().put("ok", false).put("error", it.message ?: "it failed") }
            done.countDown()
        }
        done.await(15, TimeUnit.SECONDS)
        return reply.toString()
    }

    private fun failure(text: String) = JSONObject().put("ok", false).put("error", text).toString()
}
