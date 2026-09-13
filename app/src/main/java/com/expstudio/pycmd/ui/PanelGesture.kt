package com.expstudio.pycmd.ui

import kotlin.math.abs

/**
 * Who owns a drag that started inside a plugin panel: the page, or the app's
 * scrolling list behind it.
 *
 * This is arithmetic and nothing else - no views, no Android - so it can be
 * reasoned about and tested on its own. [PluginPanelScreen]'s touch listener
 * is the part that knows about `MotionEvent` and
 * `requestDisallowInterceptTouchEvent`; this is the part that knows the rule.
 *
 * ## The rule, and the bug it replaces
 *
 * Until 2.6.1 the decision was made from one move at a time: "did the finger
 * go up or down since the last event, and has the page run out of room that
 * way?" Two things follow, and the second is the one people hit.
 *
 * A finger dragged sideways still wobbles a pixel or two up and down, so the
 * answer flipped on almost every move. And a panel shorter than the screen is
 * *both* at the top and at the bottom - `scrollY` is 0 and there is nothing
 * below - so the answer was "the list may have it" whichever way the wobble
 * went, on the very first move of every gesture.
 *
 * Dragging a slider is a sideways gesture on a panel that is often short.
 * The list took it a few pixels in and the thumb stopped following the
 * finger. Every panel has sliders, so every plugin's sliders were broken.
 *
 * Now: the direction is measured from where the finger landed, nothing is
 * decided until the gesture is big enough to have a direction, and once
 * decided it stays decided until the finger lifts.
 */
object PanelGesture {

    /** What to do with a gesture, once the finger has moved. */
    enum class Owner {
        /** Not far enough yet to tell. Hold on to it and wait. */
        UNDECIDED,

        /** The page keeps it: a sideways drag, or a control that grabs. */
        PAGE,

        /** The page has run out of room this way; the list may have it. */
        LIST,
    }

    /**
     * Who owns the gesture.
     *
     * @param dx how far the finger has moved sideways since it landed
     * @param dy how far it has moved down the screen since it landed
     * @param slop how far a drag must go before it has a direction at all
     * @param grabs the finger landed on something that owns drags outright -
     *   a slider, or an element the panel marked
     * @param pageScrolls the page scrolls an element of its own rather than
     *   the document, so asking the WebView whether it can scroll is no use
     * @param atTop the document is scrolled to the top
     * @param atBottom the document has nothing below it
     */
    fun owner(
        dx: Float,
        dy: Float,
        slop: Int,
        grabs: Boolean,
        pageScrolls: Boolean,
        atTop: Boolean,
        atBottom: Boolean,
    ): Owner {
        // A slider is a slider whichever way the finger then wanders. This
        // comes first so that a diagonal drag on one still moves the thumb.
        if (grabs) return Owner.PAGE

        if (abs(dx) < slop && abs(dy) < slop) return Owner.UNDECIDED

        // A vertical list has no business with a horizontal drag.
        if (abs(dx) > abs(dy)) return Owner.PAGE

        // Up and down. A page that scrolls an element of its own answers
        // "nowhere left to go" to both of the questions below, every time, so
        // it has to be asked rather than measured.
        if (pageScrolls) return Owner.PAGE

        // `dy` is positive when the finger moved down the screen, which drags
        // the page's content towards the bottom - so the page runs out when
        // it is already at the top.
        val towardsTop = dy > 0
        return if ((towardsTop && atTop) || (!towardsTop && atBottom)) {
            Owner.LIST
        } else {
            Owner.PAGE
        }
    }
}
