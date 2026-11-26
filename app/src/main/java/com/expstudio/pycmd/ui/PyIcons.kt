package com.expstudio.pycmd.ui

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.addPathNodes
import androidx.compose.ui.unit.dp

/**
 * The icons this app draws, defined here rather than pulled from a library.
 *
 * `material-icons-extended` ships five complete icon styles - thousands of
 * vectors - and accounted for 13.7 MB of the 24 MB dex, well over half, to
 * supply the thirty-seven glyphs below. Since a debug build does no shrinking,
 * every one of those icons rode along into the APK people have to download.
 *
 * Each entry is standard Material path data on the usual 24x24 viewport, built
 * once and reused. Tinting still works normally: `Icon(tint = ...)` applies a
 * colour filter over the black fill.
 */
object PyIcons {

    private fun icon(
        name: String,
        pathData: String,
        autoMirror: Boolean = false,
    ): ImageVector = ImageVector.Builder(
        name = name,
        defaultWidth = 24.dp,
        defaultHeight = 24.dp,
        viewportWidth = 24f,
        viewportHeight = 24f,
        autoMirror = autoMirror,
    ).apply {
        addPath(pathData = addPathNodes(pathData), fill = SolidColor(Color.Black))
    }.build()

    val Add: ImageVector by lazy {
        icon("Add", "M19,13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z")
    }

    /** A PyCmd account, signed out. */
    val Cloud: ImageVector by lazy {
        icon(
            "Cloud",
            "M19.35,10.04C18.67,6.59 15.64,4 12,4 9.11,4 6.6,5.64 5.35,8.04 2.34,8.36 0,10.91 " +
                "0,14c0,3.31 2.69,6 6,6h13c2.76,0 5,-2.24 5,-5 0,-2.64 -2.05,-4.78 -4.65,-4.96z",
        )
    }

    /** Sync now. */
    val Sync: ImageVector by lazy {
        icon(
            "Sync",
            "M12,4V1L8,5l4,4V6c3.31,0 6,2.69 6,6 0,1.01 -0.25,1.97 -0.7,2.8l1.46,1.46" +
                "C19.54,15.03 20,13.57 20,12c0,-4.42 -3.58,-8 -8,-8zM12,18c-3.31,0 -6,-2.69 " +
                "-6,-6 0,-1.01 0.25,-1.97 0.7,-2.8L5.24,7.74C4.46,8.97 4,10.43 4,12c0,4.42 " +
                "3.58,8 8,8v3l4,-4 -4,-4v3z",
        )
    }

    /** The account sheet. */
    val Person: ImageVector by lazy {
        icon(
            "Person",
            "M12,12c2.21,0 4,-1.79 4,-4s-1.79,-4 -4,-4 -4,1.79 -4,4 1.79,4 4,4zM12,14" +
                "c-2.67,0 -8,1.34 -8,4v2h16v-2c0,-2.66 -5.33,-4 -8,-4z",
        )
    }

    /** Appearance. The usual painter's palette with four wells in it. */
    val Palette: ImageVector by lazy {
        icon(
            "Palette",
            "M12,3c-4.97,0 -9,4.03 -9,9s4.03,9 9,9c0.83,0 1.5,-0.67 1.5,-1.5" +
                "c0,-0.39 -0.15,-0.74 -0.39,-1.01c-0.23,-0.26 -0.38,-0.61 -0.38,-0.99" +
                "c0,-0.83 0.67,-1.5 1.5,-1.5H16c2.76,0 5,-2.24 5,-5C21,6.58 16.97,3 12,3z" +
                "M6.5,12C5.67,12 5,11.33 5,10.5S5.67,9 6.5,9 8,9.67 8,10.5 7.33,12 6.5,12z" +
                "M9.5,8C8.67,8 8,7.33 8,6.5S8.67,5 9.5,5 11,5.67 11,6.5 10.33,8 9.5,8z" +
                "M14.5,8c-0.83,0 -1.5,-0.67 -1.5,-1.5S13.67,5 14.5,5 16,5.67 16,6.5 15.33,8 14.5,8z" +
                "M17.5,12c-0.83,0 -1.5,-0.67 -1.5,-1.5S16.67,9 17.5,9 19,9.67 19,10.5 18.33,12 17.5,12z",
        )
    }

    /** PyCmdTeach. A mortar board. */
    val School: ImageVector by lazy {
        icon(
            "School",
            "M5,13.18v4L12,21l7,-3.82v-4L12,17l-7,-3.82zM12,3L1,9l11,6 9,-4.91V17h2V9L12,3z",
        )
    }

    /** What's new. */
    val Star: ImageVector by lazy {
        icon(
            "Star",
            "M12,17.27L18.18,21l-1.64,-7.03L22,9.24l-7.19,-0.61L12,2 9.19,8.63 2,9.24" +
                "l5.46,4.73L5.82,21z",
        )
    }

    val ArrowUpward: ImageVector by lazy {
        icon("ArrowUpward", "M4,12l1.41,1.41L11,7.83V20h2V7.83l5.58,5.59L20,12l-8,-8 -8,8z")
    }

    val Clear: ImageVector by lazy {
        icon(
            "Clear",
            "M19,6.41L17.59,5 12,10.59 6.41,5 5,6.41 10.59,12 5,17.59 6.41,19 12,13.41 " +
                "17.59,19 19,17.59 13.41,12z",
        )
    }

    val BugReport: ImageVector by lazy {
        icon(
            "BugReport",
            "M20,8h-2.81c-0.45,-0.78 -1.07,-1.45 -1.82,-1.96L17,4.41 15.59,3l-2.17,2.17" +
                "C12.96,5.06 12.49,5 12,5s-0.96,0.06 -1.41,0.17L8.41,3 7,4.41l1.62,1.63" +
                "C7.88,6.55 7.26,7.22 6.81,8H4v2h2.09c-0.05,0.33 -0.09,0.66 -0.09,1v1H4v2h2v1" +
                "c0,0.34 0.04,0.67 0.09,1H4v2h2.81c1.04,1.79 2.97,3 5.19,3s4.15,-1.21 5.19,-3H20v-2" +
                "h-2.09c0.05,-0.33 0.09,-0.66 0.09,-1v-1h2v-2h-2v-1c0,-0.34 -0.04,-0.67 -0.09,-1H20V8z" +
                "M14,16h-4v-2h4V16zM14,12h-4v-2h4V12z",
        )
    }

    val ContentCopy: ImageVector by lazy {
        icon(
            "ContentCopy",
            "M16,1H4C2.9,1 2,1.9 2,3v14h2V3h12V1zM19,5H8C6.9,5 6,5.9 6,7v14c0,1.1 0.9,2 2,2h11" +
                "c1.1,0 2,-0.9 2,-2V7C21,5.9 20.1,5 19,5zM19,21H8V7h11V21z",
        )
    }

    val CreateNewFolder: ImageVector by lazy {
        icon(
            "CreateNewFolder",
            "M20,6h-8l-2,-2H4C2.9,4 2.01,4.9 2.01,6L2,18c0,1.1 0.9,2 2,2h16c1.1,0 2,-0.9 2,-2V8" +
                "c0,-1.1 -0.9,-2 -2,-2zM19,14h-3v3h-2v-3h-3v-2h3V9h2v3h3V14z",
        )
    }

    val Delete: ImageVector by lazy {
        icon(
            "Delete",
            "M6,19c0,1.1 0.9,2 2,2h8c1.1,0 2,-0.9 2,-2V7H6v12zM19,4h-3.5l-1,-1h-5l-1,1H5v2h14V4z",
        )
    }

    val Description: ImageVector by lazy {
        icon(
            "Description",
            "M14,2H6c-1.1,0 -1.99,0.9 -1.99,2L4,20c0,1.1 0.89,2 1.99,2H18c1.1,0 2,-0.9 2,-2V8l-6,-6z" +
                "M16,18H8v-2h8v2zM16,14H8v-2h8v2zM13,9V3.5L18.5,9H13z",
        )
    }

    val Dns: ImageVector by lazy {
        icon(
            "Dns",
            "M20,13H4c-0.55,0 -1,0.45 -1,1v6c0,0.55 0.45,1 1,1h16c0.55,0 1,-0.45 1,-1v-6" +
                "c0,-0.55 -0.45,-1 -1,-1zM7,19c-1.1,0 -2,-0.9 -2,-2s0.9,-2 2,-2 2,0.9 2,2 -0.9,2 -2,2z" +
                "M20,3H4c-0.55,0 -1,0.45 -1,1v6c0,0.55 0.45,1 1,1h16c0.55,0 1,-0.45 1,-1V4" +
                "c0,-0.55 -0.45,-1 -1,-1zM7,9c-1.1,0 -2,-0.9 -2,-2s0.9,-2 2,-2 2,0.9 2,2 -0.9,2 -2,2z",
        )
    }

    val Download: ImageVector by lazy {
        icon(
            "Download",
            "M12,16l-5,-5 1.41,-1.41L11,12.17V4h2v8.17l2.59,-2.58L17,11l-5,5zM6,20" +
                "c-0.55,0 -1.02,-0.2 -1.41,-0.59C4.2,19.02 4,18.55 4,18v-3h2v3h12v-3h2v3" +
                "c0,0.55 -0.2,1.02 -0.59,1.41C19.02,19.8 18.55,20 18,20L6,20z",
        )
    }

    val DriveFileRenameOutline: ImageVector by lazy {
        icon(
            "DriveFileRenameOutline",
            "M15,16l-4,4h10v-4H15zM12.06,7.19L3,16.25V20h3.75l9.06,-9.06 -3.75,-3.75z" +
                "M18.88,8.37c0.39,-0.39 0.39,-1.02 0,-1.41l-2.34,-2.34c-0.39,-0.39 -1.02,-0.39 -1.41,0" +
                "l-1.83,1.83 3.75,3.75 1.83,-1.83z",
        )
    }

    val Edit: ImageVector by lazy {
        icon(
            "Edit",
            "M3,17.25V21h3.75L17.81,9.94l-3.75,-3.75L3,17.25zM20.71,7.04c0.39,-0.39 0.39,-1.02 0,-1.41" +
                "l-2.34,-2.34c-0.39,-0.39 -1.02,-0.39 -1.41,0l-1.83,1.83 3.75,3.75 1.83,-1.83z",
        )
    }

    val FileUpload: ImageVector by lazy {
        icon("FileUpload", "M9,16h6v-6h4l-7,-7 -7,7h4zM5,18h14v2H5z")
    }

    val Folder: ImageVector by lazy {
        icon(
            "Folder",
            "M10,4H4c-1.1,0 -1.99,0.9 -1.99,2L2,18c0,1.1 0.9,2 2,2h16c1.1,0 2,-0.9 2,-2V8" +
                "c0,-1.1 -0.9,-2 -2,-2h-8l-2,-2z",
        )
    }

    val FolderOpen: ImageVector by lazy {
        icon(
            "FolderOpen",
            "M20,6h-8l-2,-2H4c-1.1,0 -1.99,0.9 -1.99,2L2,18c0,1.1 0.9,2 2,2h16c1.1,0 2,-0.9 2,-2V8" +
                "c0,-1.1 -0.9,-2 -2,-2zM20,18H4V8h16v10z",
        )
    }

    val History: ImageVector by lazy {
        icon(
            "History",
            "M13,3c-4.97,0 -9,4.03 -9,9H1l3.89,3.89 0.07,0.14L9,12H6c0,-3.87 3.13,-7 7,-7s7,3.13 7,7" +
                " -3.13,7 -7,7c-1.93,0 -3.68,-0.79 -4.94,-2.06l-1.42,1.42C8.27,19.99 10.51,21 13,21" +
                "c4.97,0 9,-4.03 9,-9s-4.03,-9 -9,-9zM12,8v5l4.28,2.54 0.72,-1.21 -3.5,-2.08V8H12z",
        )
    }

    val Info: ImageVector by lazy {
        icon(
            "Info",
            "M12,2C6.48,2 2,6.48 2,12s4.48,10 10,10 10,-4.48 10,-10S17.52,2 12,2zM13,17h-2v-6h2v6z" +
                "M13,9h-2V7h2v2z",
        )
    }

    val Inventory2: ImageVector by lazy {
        icon(
            "Inventory2",
            "M20,2H4C3,2 2,2.9 2,4v3.01C2,7.73 2.43,8.35 3,8.7V20c0,1.1 1.1,2 2,2h14c0.9,0 2,-0.9 2,-2" +
                "V8.7c0.57,-0.35 1,-0.97 1,-1.69V4C22,2.9 21,2 20,2zM15,14H9v-2h6V14zM20,7H4V4h16V7z",
        )
    }

    val MoreVert: ImageVector by lazy {
        icon(
            "MoreVert",
            "M12,8c1.1,0 2,-0.9 2,-2s-0.9,-2 -2,-2 -2,0.9 -2,2 0.9,2 2,2zM12,10c-1.1,0 -2,0.9 -2,2" +
                "s0.9,2 2,2 2,-0.9 2,-2 -0.9,-2 -2,-2zM12,16c-1.1,0 -2,0.9 -2,2s0.9,2 2,2 2,-0.9 2,-2" +
                " -0.9,-2 -2,-2z",
        )
    }

    val PlayArrow: ImageVector by lazy {
        icon("PlayArrow", "M8,5v14l11,-7z")
    }

    val Pause: ImageVector by lazy {
        icon("Pause", "M6,19h4V5H6v14zM14,5v14h4V5h-4z")
    }

    val SkipNext: ImageVector by lazy {
        icon("SkipNext", "M6,18l8.5,-6L6,6v12zM16,6v12h2V6h-2z")
    }

    val SkipPrevious: ImageVector by lazy {
        icon("SkipPrevious", "M6,6h2v12H6zM9.5,12l8.5,6V6z")
    }

    val MusicNote: ImageVector by lazy {
        icon(
            "MusicNote",
            "M12,3v10.55c-0.59,-0.34 -1.27,-0.55 -2,-0.55 -2.21,0 -4,1.79 -4,4s1.79,4 4,4 4,-1.79 4,-4" +
                "V7h4V3h-6z",
        )
    }

    val QueueMusic: ImageVector by lazy {
        icon(
            "QueueMusic",
            "M15,6H3v2h12V6zM15,10H3v2h12v-2zM3,16h8v-2H3v2zM17,6v8.18c-0.31,-0.11 -0.65,-0.18 -1,-0.18" +
                "c-1.66,0 -3,1.34 -3,3s1.34,3 3,3 3,-1.34 3,-3V8h3V6h-5z",
        )
    }

    val PlaylistAdd: ImageVector by lazy {
        icon(
            "PlaylistAdd",
            "M14,10H2v2h12v-2zM14,6H2v2h12V6zM18,14v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zM2,16h8v-2H2v2z",
        )
    }

    val Shuffle: ImageVector by lazy {
        icon(
            "Shuffle",
            "M10.59,9.17L5.41,4 4,5.41l5.17,5.17 1.42,-1.41zM14.5,4l2.04,2.04L4,18.59 5.41,20 17.96,7.46" +
                "L20,9.5V4h-5.5zM14.83,13.41l-1.41,1.41 3.13,3.13L14.5,20H20v-5.5l-2.04,2.04 -3.13,-3.13z",
        )
    }

    val Repeat: ImageVector by lazy {
        icon(
            "Repeat",
            "M7,7h10v3l4,-4 -4,-4v3H5v6h2V7zM17,17H7v-3l-4,4 4,4v-3h12v-6h-2v4z",
        )
    }

    val RepeatOne: ImageVector by lazy {
        icon(
            "RepeatOne",
            "M7,7h10v3l4,-4 -4,-4v3H5v6h2V7zM17,17H7v-3l-4,4 4,4v-3h12v-6h-2v4zM13,15V9h-1l-2,1v1h1.5v4H13z",
        )
    }

    val RestartAlt: ImageVector by lazy {
        icon(
            "RestartAlt",
            "M12,5V2L8,6l4,4V7c3.31,0 6,2.69 6,6 0,2.97 -2.17,5.43 -5,5.91v2.02c3.95,-0.49 7,-3.85 7,-7.93" +
                "c0,-4.42 -3.58,-8 -8,-8zM6,13c0,-1.65 0.67,-3.15 1.76,-4.24L6.34,7.34C4.9,8.79 4,10.79 4,13" +
                "c0,4.08 3.05,7.44 7,7.93v-2.02c-2.83,-0.48 -5,-2.94 -5,-5.91z",
        )
    }

    val Save: ImageVector by lazy {
        icon(
            "Save",
            "M17,3H5c-1.11,0 -2,0.9 -2,2v14c0,1.1 0.89,2 2,2h14c1.1,0 2,-0.9 2,-2V7l-4,-4z" +
                "M12,19c-1.66,0 -3,-1.34 -3,-3s1.34,-3 3,-3 3,1.34 3,3 -1.34,3 -3,3zM15,9H5V5h10v4z",
        )
    }

    val Stop: ImageVector by lazy {
        icon("Stop", "M6,6h12v12H6z")
    }

    val Search: ImageVector by lazy {
        icon(
            "Search",
            "M15.5,14h-0.79l-0.28,-0.27C15.41,12.59 16,11.11 16,9.5 16,5.91 13.09,3 9.5,3" +
                "S3,5.91 3,9.5 5.91,16 9.5,16c1.61,0 3.09,-0.59 4.23,-1.57l0.27,0.28v0.79" +
                "l5,4.99L20.49,19l-4.99,-5zM9.5,14C7.01,14 5,11.99 5,9.5S7.01,5 9.5,5 14,7.01 " +
                "14,9.5 11.99,14 9.5,14z",
        )
    }

    val Send: ImageVector by lazy {
        icon("Send", "M2.01,21L23,12 2.01,3 2,10l15,2 -15,2z")
    }

    val Tune: ImageVector by lazy {
        icon(
            "Tune",
            "M3,17v2h6v-2H3zM3,5v2h10V5H3zM13,21v-2h8v-2h-8v-2h-2v6h2zM7,9v2H3v2h4v2h2V9H7z" +
                "M21,13v-2H11v2h10zM15,9h2V7h4V5h-4V3h-2v6z",
        )
    }

    val Terminal: ImageVector by lazy {
        icon(
            "Terminal",
            "M20,4H4C2.89,4 2,4.9 2,6v12c0,1.1 0.89,2 2,2h16c1.1,0 2,-0.9 2,-2V6C22,4.9 21.11,4 20,4z" +
                "M20,18H4V8h16V18zM18,17h-6v-2h6V17zM7.5,17l-1.41,-1.41L8.67,13l-2.59,-2.59L7.5,9l4,4L7.5,17z",
        )
    }

    // ---- Direction-sensitive: these flip in a right-to-left layout. ----

    val OpenInFull: ImageVector by lazy {
        icon(
            "OpenInFull",
            "M21,11V3h-8l3.29,3.29 -10,10L3,13v8h8l-3.29,-3.29 10,-10z",
        )
    }

    val ExpandMore: ImageVector by lazy {
        icon("ExpandMore", "M16.59,8.59L12,13.17 7.41,8.59 6,10l6,6 6,-6z")
    }

    val ExpandLess: ImageVector by lazy {
        icon("ExpandLess", "M12,8l-6,6 1.41,1.41L12,10.83l4.59,4.58L18,14z")
    }

    val ArrowBack: ImageVector by lazy {
        icon(
            "ArrowBack",
            "M20,11H7.83l5.59,-5.59L12,4l-8,8 8,8 1.41,-1.41L7.83,13H20v-2z",
            autoMirror = true,
        )
    }

    val FormatIndentIncrease: ImageVector by lazy {
        icon(
            "FormatIndentIncrease",
            "M3,21h18v-2H3v2zM3,8v8l4,-4 -4,-4zM9,9h12V7H9v2zM3,3v2h18V3H3zM9,13h12v-2H9v2z" +
                "M9,17h12v-2H9v2z",
            autoMirror = true,
        )
    }

    val FormatIndentDecrease: ImageVector by lazy {
        icon(
            "FormatIndentDecrease",
            "M11,17h10v-2H11v2zM3,12l4,4V8l-4,4zM3,21h18v-2H3v2zM3,3v2h18V3H3zM11,9h10V7H11v2z" +
                "M11,13h10v-2H11v2z",
            autoMirror = true,
        )
    }

    val NoteAdd: ImageVector by lazy {
        icon(
            "NoteAdd",
            "M14,2H6c-1.1,0 -1.99,0.9 -1.99,2L4,20c0,1.1 0.89,2 1.99,2H18c1.1,0 2,-0.9 2,-2V8l-6,-6z" +
                "M17,15h-3v3h-2v-3H9v-2h3v-3h2v3h3v2zM13,9V3.5L18.5,9H13z",
            autoMirror = true,
        )
    }

    val Redo: ImageVector by lazy {
        icon(
            "Redo",
            "M18.4,10.6C16.55,8.99 14.15,8 11.5,8c-4.65,0 -8.58,3.03 -9.96,7.22L3.9,16" +
                "c1.05,-3.19 4.05,-5.5 7.6,-5.5 1.95,0 3.73,0.72 5.12,1.88L13,16h9V7l-3.6,3.6z",
            autoMirror = true,
        )
    }

    val Undo: ImageVector by lazy {
        icon(
            "Undo",
            "M12.5,8c-2.65,0 -5.05,0.99 -6.9,2.6L2,7v9h9l-3.62,-3.62c1.39,-1.16 3.16,-1.88 5.12,-1.88" +
                "c3.54,0 6.55,2.31 7.6,5.5l2.37,-0.78C21.08,11.03 17.15,8 12.5,8z",
            autoMirror = true,
        )
    }

    val WrapText: ImageVector by lazy {
        icon(
            "WrapText",
            "M4,19h6v-2H4V19zM20,5H4v2h16V5zM17,11H4v2h13.25c1.1,0 2,0.9 2,2s-0.9,2 -2,2H15v-2l-3,3 3,3" +
                "v-2h2c2.21,0 4,-1.79 4,-4S19.21,11 17,11z",
            autoMirror = true,
        )
    }
}
