package com.expstudio.pycmd.ui

import com.expstudio.pycmd.ui.PanelGesture.Owner
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * The rule that decides who owns a drag inside a plugin panel.
 *
 * The first three checks are the bug that broke every plugin's sliders in
 * 2.6.0, written as the shapes that caused it: a sideways drag, a panel
 * shorter than the screen, and the pixel of vertical wobble that comes with
 * any real finger.
 */
class PanelGestureTest {

    private val slop = 16

    private fun owner(
        dx: Float,
        dy: Float,
        grabs: Boolean = false,
        pageScrolls: Boolean = false,
        atTop: Boolean = true,
        atBottom: Boolean = true,
    ) = PanelGesture.owner(dx, dy, slop, grabs, pageScrolls, atTop, atBottom)

    // -- the bug -----------------------------------------------------------

    @Test
    fun `a sideways drag belongs to the page`() {
        assertEquals(Owner.PAGE, owner(dx = 80f, dy = 0f))
        assertEquals(Owner.PAGE, owner(dx = -80f, dy = 0f))
    }

    @Test
    fun `a sideways drag with a wobble still belongs to the page`() {
        // A real finger is never exactly level. This is the case that broke:
        // one pixel down, on a panel that is both at the top and the bottom.
        assertEquals(Owner.PAGE, owner(dx = 80f, dy = 1f))
        assertEquals(Owner.PAGE, owner(dx = 80f, dy = -1f))
        assertEquals(Owner.PAGE, owner(dx = 80f, dy = 20f))
    }

    @Test
    fun `a panel shorter than the screen does not lose a sideways drag`() {
        // Short panel: nothing above, nothing below, both answers true.
        assertEquals(Owner.PAGE, owner(dx = 60f, dy = 2f, atTop = true, atBottom = true))
    }

    // -- what a slider gets ------------------------------------------------

    @Test
    fun `a control that grabs keeps the gesture whichever way it goes`() {
        assertEquals(Owner.PAGE, owner(dx = 0f, dy = 90f, grabs = true))
        assertEquals(Owner.PAGE, owner(dx = 0f, dy = -90f, grabs = true))
        assertEquals(Owner.PAGE, owner(dx = 3f, dy = 3f, grabs = true))
    }

    @Test
    fun `and it does not have to travel first`() {
        // Below the slop, and still the page's: waiting to be sure would mean
        // a slider that ignores the first few pixels of every drag.
        assertEquals(Owner.PAGE, owner(dx = 1f, dy = 1f, grabs = true))
    }

    // -- nothing decided too early ----------------------------------------

    @Test
    fun `a drag too small to have a direction is nobody's yet`() {
        assertEquals(Owner.UNDECIDED, owner(dx = 0f, dy = 0f))
        assertEquals(Owner.UNDECIDED, owner(dx = 15f, dy = 15f))
        assertEquals(Owner.UNDECIDED, owner(dx = -15f, dy = 4f))
    }

    @Test
    fun `and the slop is a distance, not a count of events`() {
        assertEquals(Owner.UNDECIDED, owner(dx = (slop - 1).toFloat(), dy = 0f))
        assertEquals(Owner.PAGE, owner(dx = (slop + 1).toFloat(), dy = 0f))
    }

    // -- scrolling up and down still works the way it did ------------------

    @Test
    fun `scrolling down through a panel that has more below is the page's`() {
        assertEquals(Owner.PAGE, owner(dx = 0f, dy = -80f, atTop = true, atBottom = false))
    }

    @Test
    fun `scrolling up at the top hands it to the list`() {
        // Pulling the content down when there is nothing above: the list
        // should take over, so a flick past the panel still works.
        assertEquals(Owner.LIST, owner(dx = 0f, dy = 80f, atTop = true, atBottom = false))
    }

    @Test
    fun `scrolling down at the bottom hands it to the list`() {
        assertEquals(Owner.LIST, owner(dx = 0f, dy = -80f, atTop = false, atBottom = true))
    }

    @Test
    fun `but not in the middle of a long panel`() {
        assertEquals(Owner.PAGE, owner(dx = 0f, dy = 80f, atTop = false, atBottom = false))
        assertEquals(Owner.PAGE, owner(dx = 0f, dy = -80f, atTop = false, atBottom = false))
    }

    @Test
    fun `a page that scrolls an element of its own always keeps it`() {
        // Such a page answers "nowhere left to go" to both questions, every
        // time, so measuring would always hand the drag away.
        assertEquals(
            Owner.PAGE,
            owner(dx = 0f, dy = 80f, pageScrolls = true, atTop = true, atBottom = true),
        )
        assertEquals(
            Owner.PAGE,
            owner(dx = 0f, dy = -80f, pageScrolls = true, atTop = true, atBottom = true),
        )
    }

    // -- exactly diagonal --------------------------------------------------

    @Test
    fun `a drag at exactly forty-five degrees is treated as up and down`() {
        // It has to be one or the other; up and down is the safer guess,
        // because that is the gesture a list is waiting for and a page that
        // wanted it would have said so.
        assertEquals(
            Owner.LIST,
            owner(dx = 80f, dy = 80f, atTop = true, atBottom = true),
        )
    }
}
