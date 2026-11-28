# What R8 must not touch.
#
# The rule of thumb here is "anything reached by name rather than by a call":
# R8 renames what it can prove is only ever called from Kotlin, and everything
# below is called from somewhere it cannot see - Python, JavaScript, or the
# Android manifest.

# Chaquopy's runtime, and the Java classes Python reflects on to reach it.
-keep class com.chaquo.python.** { *; }

# This app's own classes, kept whole. They are a small share of the dex - the
# saving is in the libraries - and several of them are called by name from
# Python (the output sink, the progress sink, the JavaScript file runner) or
# from JavaScript inside a WebView. Keeping the lot costs a little size and
# removes a class of bug that only ever shows up on a phone.
-keep class com.expstudio.pycmd.** { *; }

# Methods a WebView calls from JavaScript. The class may be renamed - the JS
# side reaches it through the name it was injected under - but the methods
# cannot be.
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}

# Kotlin metadata, so anything that does reflect on a Kotlin class still can.
-keep class kotlin.Metadata { *; }

# Line numbers in a stack trace are the difference between a bug report worth
# reading and "it crashed". The file name is renamed away; the numbers stay.
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile

# PyCmd's language engine. Python calls it by class and method name through
# Chaquopy (pcmd_engine.py), and implements PcmdIO from the Python side - so
# none of it may be renamed or dropped.
-keep class com.expstudio.pycmd.lang.** { *; }
