package com.expstudio.pycmd.util

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The rule that decides whether this is an emulator.
 *
 * Split out of [Device] so it can be given made-up signals: a unit test cannot
 * change `Build.FINGERPRINT`, and the interesting part is not reading those
 * fields but what is concluded from them.
 *
 * The cost of being wrong is small in both directions - the app shows a
 * different card in System and nothing else changes - but it is the card
 * people are asked to paste when PyCmd will not start, so it should not lie.
 */
class DeviceTest {

    private fun signals(vararg on: String): Map<String, Boolean> =
        listOf(
            "fingerprint", "model", "brand", "product",
            "hardware", "manufacturer", "qemu-files",
        ).associateWith { it in on }

    @Test
    fun `a phone trips nothing`() {
        assertFalse(Device.looksEmulated(signals()))
    }

    @Test
    fun `the emulated board names are enough on their own`() {
        // goldfish and ranchu are Android's own emulated boards and nothing
        // else uses either name.
        assertTrue(Device.looksEmulated(signals("hardware")))
    }

    @Test
    fun `a qemu device node is enough on its own`() {
        assertTrue(Device.looksEmulated(signals("qemu-files")))
    }

    @Test
    fun `one brand string is not enough`() {
        // A Pixel reports a google brand; cheap tablets ship with generic
        // product names. Either one alone has to be allowed to be a real phone.
        assertFalse(Device.looksEmulated(signals("brand")))
        assertFalse(Device.looksEmulated(signals("product")))
        assertFalse(Device.looksEmulated(signals("manufacturer")))
        assertFalse(Device.looksEmulated(signals("model")))
        assertFalse(Device.looksEmulated(signals("fingerprint")))
    }

    @Test
    fun `two agreeing is enough`() {
        assertTrue(Device.looksEmulated(signals("brand", "product")))
        assertTrue(Device.looksEmulated(signals("fingerprint", "model")))
        assertTrue(Device.looksEmulated(signals("manufacturer", "model")))
    }

    @Test
    fun `a standard emulator trips most of them`() {
        assertTrue(
            Device.looksEmulated(
                signals("fingerprint", "model", "brand", "product", "hardware"),
            ),
        )
    }

    @Test
    fun `an unknown signal map is not an emulator`() {
        // A map with none of the expected keys - which is what a future
        // refactor that renames one would produce - must not flip the answer.
        assertFalse(Device.looksEmulated(mapOf("something-else" to true)))
        assertFalse(Device.looksEmulated(emptyMap()))
    }
}
