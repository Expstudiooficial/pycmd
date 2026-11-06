package com.expstudio.pycmd

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build
import com.expstudio.pycmd.python.ServerService
import com.expstudio.pycmd.plugins.CustomPlugins
import com.expstudio.pycmd.plugins.Plugins
import com.expstudio.pycmd.util.Branding
import com.expstudio.pycmd.util.UpdateWorker
import com.expstudio.pycmd.util.DebugLog
import com.expstudio.pycmd.util.Device

class PyCmdApp : Application() {

    override fun onCreate() {
        super.onCreate()
        // Installed before anything else so a crash during start-up is still
        // recorded for the debug console.
        DebugLog.installCrashHandler()
        DebugLog.info("app", "${Branding.NAME} starting")
        // Before anything is drawn: see Branding for what this is and why it
        // cannot fire on a build that still says what it is.
        Branding.verify(this)
        // Written down before anything else happens, because the first thing
        // worth knowing about a crash on start-up is what kind of machine it
        // was on and whether this build had Python for it.
        Device.log(this)
        Plugins.init(this)
        CustomPlugins.init(this)
        createNotificationChannel()
        // Put back on every start, because a force-stop cancels scheduled work
        // and nothing else would ever notice.
        UpdateWorker.sync(this)
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val channel = NotificationChannel(
            ServerService.CHANNEL_ID,
            getString(R.string.server_channel_name),
            NotificationManager.IMPORTANCE_LOW,
        ).apply {
            description = getString(R.string.server_channel_desc)
            setShowBadge(false)
        }
        val manager = getSystemService(NotificationManager::class.java) ?: return
        manager.createNotificationChannel(channel)

        // A second channel, so somebody who wants the server notification but
        // not update notices can have exactly that.
        manager.createNotificationChannel(
            NotificationChannel(
                UpdateWorker.CHANNEL_ID,
                getString(R.string.update_channel_name),
                NotificationManager.IMPORTANCE_LOW,
            ).apply {
                description = getString(R.string.update_channel_desc)
                setShowBadge(false)
            },
        )
    }
}
