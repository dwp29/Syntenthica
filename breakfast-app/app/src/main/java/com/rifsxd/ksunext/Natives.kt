package com.rifsxd.ksunext

/**
 * Bridge to libkernelsu.so.
 *
 * This package name is not a mistake or a leftover: JNI looks symbols up by
 * their fully-qualified class name, and the library exports
 * Java_com_rifsxd_ksunext_Natives_getKernelUAPIVersion. Moving this class would
 * break the binding at runtime, not at compile time, so it stays where the
 * library expects it.
 *
 * Only the two UAPI getters are declared. The rest of the library's surface is
 * deliberately not exposed to this app.
 */
object Natives {

    init {
        System.loadLibrary("kernelsu")
    }

    val kernelUAPIVersion: Int
        external get

    val managerUAPIVersion: Int
        external get
}
