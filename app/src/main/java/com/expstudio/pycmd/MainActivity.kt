package com.expstudio.pycmd

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.CompositionLocalProvider
import androidx.core.content.ContextCompat
import com.expstudio.pycmd.ui.Appearance
import com.expstudio.pycmd.ui.LocalAppearance
import com.expstudio.pycmd.ui.PanelViews
import com.expstudio.pycmd.ui.PyCmdRoot
import com.expstudio.pycmd.ui.PyCmdTheme

class MainActivity : ComponentActivity() {

    /**
     * Asked for once, up front: without it the foreground-service notification
     * that keeps servers alive is silently dropped on Android 13+.
     */
    private val notificationPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    /**
     * The theme, read off disk before anything is drawn.
     *
     * An activity field and not a `remember`, because it is read while the
     * first composition is being built and has to already have the answer.
     */
    private lateinit var appearance: Appearance

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        requestNotificationPermissionIfNeeded()
        appearance = Appearance(this)

        setContent {
            CompositionLocalProvider(LocalAppearance provides appearance) {
                PyCmdTheme(
                    theme = appearance.theme,
                    corner = appearance.corner,
                    reducedMotion = appearance.reducedMotion,
                    textScale = appearance.textScale,
                ) {
                    PyCmdRoot()
                }
            }
        }
    }

    /**
     * Lets go of the plugin panels kept warm between visits.
     *
     * They hold this activity's context, so they cannot outlive it. After
     * `super`, deliberately: tearing the composition down is what parks them,
     * and clearing before that would clear an empty pool and then fill it with
     * views belonging to a screen that no longer exists.
     */
    override fun onDestroy() {
        super.onDestroy()
        PanelViews.clear()
    }

    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
        val granted = ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED
        if (!granted) {
            notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }
}
