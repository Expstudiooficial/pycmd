package com.expstudio.pycmd.util

import com.expstudio.pycmd.BuildConfig
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The changelog that ships in the APK.
 *
 * The one thing worth asserting is that it describes the build it is inside:
 * the what's-new screen is shown automatically after an update, and a screen
 * that confidently lists the previous release's changes is worse than no
 * screen. Everything else here is tidiness.
 */
class ReleaseNotesTest {

    @Test
    fun `this build has notes`() {
        val current = ReleaseNotes.current
        assertNotNull(
            "no entry in ReleaseNotes for versionCode ${BuildConfig.VERSION_CODE}",
            current,
        )
        assertEquals(BuildConfig.VERSION_CODE, current!!.versionCode)
    }

    @Test
    fun `the version name matches the build`() {
        // The debug build adds a suffix, so compare the front of it.
        val name = ReleaseNotes.current!!.versionName
        assertTrue(
            "notes say $name, the build says ${BuildConfig.VERSION_NAME}",
            BuildConfig.VERSION_NAME.startsWith(name),
        )
    }

    @Test
    fun `the newest entry is first`() {
        val codes = ReleaseNotes.ALL.map { it.versionCode }
        assertEquals(codes.sortedDescending(), codes)
        assertEquals(codes.size, codes.toSet().size)
    }

    @Test
    fun `every entry says something`() {
        for (release in ReleaseNotes.ALL) {
            assertTrue("${release.versionName} has no headline", release.headline.length > 10)
            assertTrue("${release.versionName} lists no changes", release.total > 0)
            for (line in release.added + release.fixed + release.removed) {
                assertTrue("a change in ${release.versionName} is too terse", line.length > 15)
            }
        }
    }

    @Test
    fun `forVersion finds what is there and nothing else`() {
        assertNotNull(ReleaseNotes.forVersion(BuildConfig.VERSION_CODE))
        org.junit.Assert.assertNull(ReleaseNotes.forVersion(-1))
    }
}
