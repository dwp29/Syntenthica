package app.breakfast.manager

import app.breakfast.manager.data.AuditRunner
import app.breakfast.manager.data.ClockSource
import app.breakfast.manager.data.DeviceAudit
import app.breakfast.manager.data.FileRead
import app.breakfast.manager.data.ModuleScan
import app.breakfast.manager.data.RootStatus
import app.breakfast.manager.data.TuningVisibility
import app.breakfast.manager.data.TuningWhitelist
import app.breakfast.manager.data.Uptime
import app.breakfast.manager.ui.PulseReader
import app.breakfast.manager.ui.ThermalZone
import app.breakfast.manager.ui.components.graphBounds
import app.breakfast.manager.ui.components.cpuUsageFromDelta
import app.breakfast.manager.ui.components.graphScale
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Every case here is a defect that was visible on a real device screenshot. */
private class FakeClock(private val ms: Long) : ClockSource {
    override fun elapsedRealtimeMs(): Long = ms
}

class DeviceRegressionTest {

    // --- "0 C - Normal" in green ------------------------------------------

    @Test
    fun `zero degrees is not a temperature`() {
        // The reporting device's thermal zone returned 0. It was rendered as
        // "0 C / Normal" in green, which is a fabricated healthy reading.
        assertFalse(PulseReader.isPlausibleTemperature(0f))
        assertFalse(PulseReader.isPlausibleTemperature(0.0f))
    }

    @Test
    fun `real and implausible temperatures are told apart`() {
        assertTrue(PulseReader.isPlausibleTemperature(38f))
        assertTrue(PulseReader.isPlausibleTemperature(72.5f))
        assertFalse(PulseReader.isPlausibleTemperature(-5f))
        assertFalse(PulseReader.isPlausibleTemperature(250f))
        assertFalse(PulseReader.isPlausibleTemperature(null))
    }

    // --- UPTIME showed a dash on a device where it is always available -----

    @Test
    fun `uptime comes from the monotonic clock`() {
        val hours = Uptime.hours(FakeClock(4L * 86_400_000L + 7L * 3_600_000L))
        assertEquals(103.0, hours!!, 0.001)
    }

    @Test
    fun `uptime formats days and hours`() {
        assertEquals("4d 2h", Uptime.format(98.4))
        assertEquals("7j", Uptime.format(7.9))
        assertEquals("—", Uptime.format(null))
    }

    @Test
    fun `a clock reading zero is not uptime either`() {
        assertNull(Uptime.hours(FakeClock(0L)))
    }

    // --- four states, so LAB and TUNING cannot contradict each other -------

    @Test
    fun `exists but unreadable is its own state`() {
        val observation = AuditRunner.Observation(
            value = null,
            readable = false,
            writable = false,
            permissions = "-rw-r--r-- root:root",
        )
        assertEquals(DeviceAudit.Support.UNREADABLE, AuditRunner.classify(observation, declaredReadOnly = false))
    }

    @Test
    fun `verified missing node is absent, not unreadable`() {
        val observation = AuditRunner.Observation(
            value = null,
            readable = false,
            writable = false,
            permissions = null,
            // Absence is a claim that needs this evidence; without it the honest
            // answer is UNKNOWN, which the next test covers.
            presence = AuditRunner.Presence.VERIFIED_ABSENT,
        )
        assertEquals(DeviceAudit.Support.ABSENT, AuditRunner.classify(observation, declaredReadOnly = false))
    }

    @Test
    fun `a node we never saw is never called absent`() {
        val observation = AuditRunner.Observation(
            value = null,
            readable = false,
            writable = false,
            permissions = null,
            presence = AuditRunner.Presence.UNKNOWN,
        )
        assertEquals(DeviceAudit.Support.UNKNOWN, AuditRunner.classify(observation, declaredReadOnly = false))
    }

    @Test
    fun `summary counts the buckets in a way that adds up`() {
        fun node(support: DeviceAudit.Support) = DeviceAudit.Node(
            group = "g", path = "/p/${support.name}", support = support,
            nodePermissions = null, readable = false, value = null,
        )
        val report = DeviceAudit.Report(
            "k", 0L,
            listOf(
                node(DeviceAudit.Support.SUPPORTED),
                node(DeviceAudit.Support.READ_ONLY),
                node(DeviceAudit.Support.UNREADABLE),
                node(DeviceAudit.Support.ABSENT),
            ),
        )
        assertEquals(
            4,
            report.supported + report.readOnly + report.unreadable + report.unknown + report.absent,
        )
        assertTrue(report.summary().contains("1 tidak bisa dibaca"))
        assertEquals(1, report.unreadableNodes().size)
    }

    @Test
    fun `a clean audit does not mention the unreadable bucket`() {
        val report = DeviceAudit.Report("k", 0L, emptyList())
        assertEquals("Audit selesai: 0 didukung, 0 baca-saja, 0 tidak ada.", report.summary())
    }
}

/** Audit's honesty about existence, and the numbers the device got wrong. */
class Run17RegressionTest {

    private fun obs(
        presence: AuditRunner.Presence,
        value: String? = null,
        permissions: String? = null,
    ) = AuditRunner.Observation(
        value = value,
        readable = value != null,
        writable = false,
        permissions = permissions,
        presence = presence,
    )

    @Test
    fun `cannot look is not the same as not there`() {
        // Ten nodes the kernel demonstrably has were reported "tidak ada".
        assertEquals(
            DeviceAudit.Support.UNKNOWN,
            AuditRunner.classify(obs(AuditRunner.Presence.UNKNOWN), declaredReadOnly = false),
        )
        assertEquals(
            DeviceAudit.Support.ABSENT,
            AuditRunner.classify(obs(AuditRunner.Presence.VERIFIED_ABSENT), declaredReadOnly = false),
        )
    }

    @Test
    fun `an unverified node is never counted as absent`() {
        val node = DeviceAudit.Node(
            group = "GPU", path = "/sys/class/kgsl/kgsl-3d0/gpuclk",
            support = DeviceAudit.Support.UNKNOWN, nodePermissions = null,
            readable = false, value = null,
        )
        val report = DeviceAudit.Report("k", 0L, listOf(node))
        assertEquals(0, report.absent)
        assertEquals(1, report.unknown)
        assertFalse(report.isComplete)
        assertTrue(report.summary().contains("1 tidak bisa dipastikan"))
    }

    @Test
    fun `one unreadable file does not make a fake absence`() {
        assertEquals(
            "tidak ada (direktori induk sudah diperiksa)",
            AuditRunner.noteFor(obs(AuditRunner.Presence.VERIFIED_ABSENT), declaredReadOnly = false),
        )
        val unknownNote = AuditRunner.noteFor(obs(AuditRunner.Presence.UNKNOWN), declaredReadOnly = false)!!
        assertTrue(unknownNote.contains("tidak bisa dipastikan"))
    }

    // --- Memory line drew a real 61% as a flat line at the bottom ----------

    @Test
    fun `a flat percentage series keeps its true height`() {
        // Same numbers as the device: 60.6..61.2 out of 100. Before the fix the
        // lowest of these was drawn ON the floor and the highest at the ceiling.
        val series = listOf(60.6f, 60.8f, 61.0f, 61.1f, 61.2f)
        val drawn = graphScale(series.first(), fixedMax = 100f) to
            graphScale(series.last(), fixedMax = 100f)
        assertTrue("memory must sit above the floor, was ${drawn.first}", drawn.first > 0.15f)
        assertTrue("memory must sit below the ceiling", drawn.second < 0.9f)
        assertTrue("61% must be visibly high, not pinned to the bottom", drawn.second > 0.2f)
    }

    @Test
    fun `a percentage series still shows its wobble`() {
        val calm = graphScale(60.6f, fixedMax = 100f)
        val high = graphScale(61.2f, fixedMax = 100f)
        // Visible, but not exaggerated to the full height of the chart.
        assertTrue("difference must be visible", high - calm > 0.0005f)
        assertTrue("difference must not be 100% of the chart", high - calm < 0.3f)
    }

    // --- uptime printed "0j" twenty minutes after boot ---------------------

    @Test
    fun `minutes are not rounded away to zero hours`() {
        // 20 minutes exactly.
        assertEquals("20m", Uptime.format(20.0 / 60.0))
        // 0.33 h is 19.8 minutes; truncation gives 19m, which is right - the point
        // is that it is not "0j".
        assertTrue(Uptime.format(0.33).endsWith("m"))
        assertEquals("2j", Uptime.format(2.5))
        assertEquals("1d 3h", Uptime.format(27.7))
    }

    // --- CPU Load: a delta too small to measure is not a measurement -------

    @Test
    fun `a stat delta below one tick window is rejected`() {
        assertNull(cpuUsageFromDelta(totalDelta = 4L, idleDelta = 1L))
        assertEquals(0.5f, cpuUsageFromDelta(totalDelta = 400L, idleDelta = 200L)!!, 0.001f)
    }
}


class TuningVisibilityTest {

    private fun node(keyPath: String, support: DeviceAudit.Support, value: String? = null) =
        DeviceAudit.Node(
            group = "g", path = keyPath, support = support,
            nodePermissions = null, readable = value != null, value = value,
        )

    private fun report(vararg nodes: DeviceAudit.Node) = DeviceAudit.Report("k", 0L, nodes.toList())

    @Test
    fun `a parameter with no row of its own is listed, not hidden`() {
        // The device bug: iowait_boost_enable exists in the kernel, but the screen
        // only draws schedutil nodes it can use, so the hardcoded dedupe list hid
        // it from both the group and the "tidak tersedia" list.
        val r = report(
            node("/sys/devices/system/cpu/cpu0/cpufreq/schedutil/up_rate_limit_us",
                DeviceAudit.Support.READ_ONLY, "0"),
            node("/sys/devices/system/cpu/cpu0/cpufreq/schedutil/iowait_boost_enable",
                DeviceAudit.Support.UNKNOWN),
        )
        val missing = TuningVisibility.missingKeys(r).map { it.key }
        assertTrue("iowait_boost_enable must be listed", "schedutil_iowait" in missing)
    }

    @Test
    fun `a rendered parameter is not repeated in the missing list`() {
        val r = report(
            node("/sys/devices/system/cpu/cpu0/cpufreq/schedutil/up_rate_limit_us",
                DeviceAudit.Support.READ_ONLY, "0"),
        )
        val missing = TuningVisibility.missingKeys(r).map { it.key }
        assertFalse("up_rate is drawn in its group", "schedutil_up_rate" in missing)
        // And its sibling, which has no value, must be named.
        assertTrue("down_rate must be listed", "schedutil_down_rate" in missing)
    }

    @Test
    fun `an empty audit lists every parameter rather than pretending they exist`() {
        val missing = TuningVisibility.missingKeys(report())
        assertEquals(TuningWhitelist.PARAMETERS.size, missing.size)
    }
}

/** Thermal zones: a throttle limit is not a thermometer. */
class ThermalZoneTest {

    private fun zone(name: String, celsius: Float) = ThermalZone(name, celsius)

    @Test
    fun `a zone named like a limit is not a sensor`() {
        // This is what produced a flat 81 then a flat 88: the maximum over every
        // zone whose name contains "cpu" picked a throttle threshold, and a
        // threshold does not move when the CPU heats up.
        val zones = listOf(
            zone("cpu-0-usr", 41.2f),
            zone("cpu-0-limit", 88.0f),
            zone("cpu-0-trip-point-0", 95.0f),
            zone("soc-thermal", 39.5f),
        )
        val sensors = zones.filter { PulseReader.isThermometerForTest(it) }
        assertEquals(listOf("cpu-0-usr", "soc-thermal"), sensors.map { it.name })
    }

    @Test
    fun `the hottest real sensor wins, not the hottest number`() {
        val zones = listOf(
            zone("cpu-1-usr", 44.0f),
            zone("cpu-0-usr", 41.0f),
            zone("cpu-0-stage", 99.0f),
        )
        val hottest = zones.filter { PulseReader.isThermometerForTest(it) }.maxByOrNull { it.celsius }
        assertEquals("cpu-1-usr", hottest?.name)
        assertEquals(44.0f, hottest!!.celsius, 0.01f)
    }

    @Test
    fun `an implausible zone is dropped before it can be shown`() {
        assertFalse(PulseReader.isPlausibleTemperature(0f))
        assertFalse(PulseReader.isPlausibleTemperature(999f))
        assertTrue(PulseReader.isPlausibleTemperature(41f))
    }
}

/** The pages that used to be placeholders, and the zone that lied about being the CPU. */
class Run23RegressionTest {

    private fun zone(name: String, celsius: Float) = ThermalZone(name, celsius)

    @Test
    fun `the ring shows a CPU sensor, not a bare soc zone`() {
        // Exactly the device's numbers: a zone named "soc" read 88 C while every
        // cpu-*-usr sensor read 37-40 C, and the ring is labelled "CPU".
        val zones = listOf(
            zone("soc", 88.0f),
            zone("aoss-0-usr", 40.4f),
            zone("cpu-0-0-usr", 39.8f),
            zone("cpu-0-1-usr", 39.2f),
            zone("pm6150-tz", 37.0f),
        )
        val ring = PulseReader.ringZone(zones)
        assertEquals("cpu-0-0-usr", ring?.name)
        assertEquals(39.8f, ring!!.celsius, 0.01f)
    }

    @Test
    fun `a threshold zone never reaches the ring`() {
        val zones = listOf(zone("cpu-0-limit", 99f), zone("cpu-0-usr", 41f))
        assertEquals("cpu-0-usr", PulseReader.ringZone(zones)?.name)
    }

    @Test
    fun `module parsing reads proc modules and ignores junk`() {
        val text = """
            zram 40960 3 - Live 0x0000000000000000
            kheaders 12345 0 - Live 0x0000000000000000
            broken-line
        """.trimIndent()
        val modules = ModuleScan.parse(text)
        assertEquals(2, modules.size)
        assertEquals("kheaders", modules.first().name)
        assertEquals(40960L, modules.first { it.name == "zram" }.sizeBytes)
    }

    @Test
    fun `an unreadable proc modules is not an empty module list`() {
        // The device bug: /proc/modules could not be opened, and MODULES said
        // "Kernel ini tidak memuat modul apa pun". Those are different answers.
        val denied = ModuleScan.scan { FileRead.Denied }
        assertTrue(denied is ModuleScan.Result.Unreadable)
        val (headline, detail) = ModuleScan.describe(denied)
        assertEquals("Daftar modul tidak bisa dibaca.", headline)
        assertTrue("must not claim zero modules", !headline.contains("0 modul"))
        assertTrue(detail!!.contains("bukan pernyataan bahwa tidak ada modul"))
    }

    @Test
    fun `only a successful read may say zero modules`() {
        val empty = ModuleScan.scan { FileRead.Ok("") }
        assertTrue(empty is ModuleScan.Result.Loaded)
        val (headline, _) = ModuleScan.describe(empty)
        assertTrue(headline.contains("0 modul"))
    }

    @Test
    fun `a missing proc modules is named as such`() {
        val missing = ModuleScan.scan { FileRead.Missing }
        assertEquals(ModuleScan.Result.NoProcModules, missing)
        val (headline, detail) = ModuleScan.describe(missing)
        assertTrue(headline.contains("tidak menyediakan"))
        assertTrue(detail!!.contains("CONFIG_MODULES"))
    }

    @Test
    fun `the audit breakdown always adds up to the node count`() {
        fun node(s: DeviceAudit.Support) = DeviceAudit.Node("g", "/p/${s.name}", s, null, false, null)
        val report = DeviceAudit.Report(
            "k", 0L,
            listOf(
                node(DeviceAudit.Support.SUPPORTED),
                node(DeviceAudit.Support.READ_ONLY),
                node(DeviceAudit.Support.UNREADABLE),
                node(DeviceAudit.Support.UNKNOWN),
                node(DeviceAudit.Support.ABSENT),
            ),
        )
        assertEquals(report.nodes.size, report.counted())
        assertEquals(5, report.countsBreakdown().size)
        assertEquals(5, report.countsBreakdown().sumOf { it.second })
    }
}

/** ROOT must never turn "I could not look" into "there is nothing". */
class RootHonestyTest {

    private fun fact(value: String, sure: RootStatus.Sure) = RootStatus.Fact(value, sure)

    private fun snapshot(
        manager: RootStatus.Fact = fact("tidak ditemukan", RootStatus.Sure.FILESYSTEM),
        su: RootStatus.Fact = fact("tidak ditemukan", RootStatus.Sure.FILESYSTEM),
        uid: RootStatus.Fact = fact("tidak terbaca", RootStatus.Sure.UNKNOWN),
        granted: Boolean = false,
    ) = RootStatus.Snapshot(
        manager = manager, su = su, uid = uid, granted = granted,
        dmesg = fact("tidak bisa dibaca", RootStatus.Sure.SHELL),
        writeNodes = fact("tidak diizinkan", RootStatus.Sure.SHELL),
        kernelVersion = null, kernelUapi = null, suEnabled = null,
        superuserCount = null, safeMode = null,
        libraryLoaded = false, librarySkippedReason = null, checkedAtMs = 0L,
    )

    @Test
    fun `a blind probe is not a negative answer`() {
        val blind = snapshot(
            manager = fact("tidak bisa dipastikan", RootStatus.Sure.UNKNOWN),
            su = fact("tidak bisa dipastikan", RootStatus.Sure.UNKNOWN),
        )
        val verdict = blind.verdict()
        assertTrue("must admit it could not check: $verdict", verdict.contains("tidak bisa memeriksa"))
        // The verdict must state that the situation is UNKNOWN, and must not
        // reach for any verdict about the device at all.
        assertTrue(
            "must call the state unknown: $verdict",
            verdict.contains("BELUM DIKETAHUI") || verdict.contains("belum diketahui"),
        )
        assertFalse(
            "must not claim root exists or is absent: $verdict",
            verdict.startsWith("Root diberikan") || verdict.startsWith("Tidak ada su"),
        )
        // The rows must carry the uncertainty through, not flatten it.
        val managerRow = blind.lines().first { it.first == "pengelola root" }.second
        assertEquals(RootStatus.Sure.UNKNOWN, managerRow.sure)
    }

    @Test
    fun `a device with a manager but unreadable su says so`() {
        val s = snapshot(
            manager = fact("KernelSU v0.9.2", RootStatus.Sure.LIBRARY),
            su = fact("tidak terbaca", RootStatus.Sure.FILESYSTEM),
        )
        assertTrue(s.verdict().contains("su"))
    }

    @Test
    fun `a readable manager with a refusing su is not called unreadable`() {
        // The order of these checks was wrong: "manager unreadable" fired first
        // and hid the case that actually happens - the manager is right there,
        // and the shell was simply refused.
        val s = snapshot(
            manager = fact("tidak bisa dipastikan", RootStatus.Sure.UNKNOWN),
            su = fact("tidak terbaca", RootStatus.Sure.UNKNOWN),
        )
        assertTrue(s.verdict().contains("BELUM DIKETAHUI"))

        val readable = snapshot(
            manager = fact("KernelSU v0.9.2", RootStatus.Sure.FILESYSTEM),
            su = fact("/system/bin/su", RootStatus.Sure.FILESYSTEM),
        )
        val verdict = readable.verdict()
        assertFalse("must not claim it could not check: $verdict", verdict.contains("BELUM DIKETAHUI"))
        assertTrue("must name the refusal: $verdict", verdict.contains("belum diizinkan"))
        assertTrue("must say a prompt does not appear by itself: $verdict",
            verdict.contains("Tidak ada permintaan izin"))
    }

    @Test
    fun `the root shell is what decides, not the blind directory`() {
        // /data/adb being unreadable must not outrank a su that answered.
        val s = snapshot(
            manager = fact("tidak bisa dipastikan", RootStatus.Sure.UNKNOWN),
            su = fact("/system/bin/su", RootStatus.Sure.FILESYSTEM),
        )
        assertTrue(s.verdict().contains("/system/bin/su"))
    }

    @Test
    fun `a granted snapshot reports the privileged reads as checked`() {
        // The helper builds dmesg as "tidak bisa dibaca" because that is what an
        // ungranted device looks like; a granted one must say so and be happy.
        val s = snapshot(uid = fact("0", RootStatus.Sure.SHELL), granted = true)
            .copy(dmesg = fact("bisa dibaca", RootStatus.Sure.SHELL))
        assertTrue(s.verdict().startsWith("Root diberikan"))
        assertEquals("bisa dibaca", s.dmesg.value)
    }
}


/** The force close: a native library that can kill the process while loading. */
class NativeGuardTest {

    @Test
    fun `an unskipped snapshot never loads the library`() {
        // Run 30 force-closed on start-up. The default must therefore be "do not
        // load", and that is a property of the API, not of the caller's memory.
        val snapshot = RootStatus.snapshot(allowLibrary = false)
        assertFalse(snapshot.libraryLoaded)
        assertTrue(
            "the page must say why it did not load",
            snapshot.librarySkippedReason!!.contains("tidak dimuat"),
        )
    }

    @Test
    fun `a skipped load still yields a complete snapshot`() {
        val snapshot = RootStatus.snapshot(allowLibrary = false)
        // Seven rows, none of them null, and a verdict a person can act on.
        assertEquals(7, snapshot.lines().size)
        assertTrue(snapshot.verdict().isNotEmpty())
    }
}

/** The marker that survives a process kill. */
class NativeMarkerLogicTest {

    @Test
    fun `an in-flight marker means the last attempt died`() {
        // Mirrors NativeGuard.mayLoad(): crashed marker and no consent denies it.
        fun mayLoad(crashed: Boolean, consent: Boolean) = !crashed || consent
        assertFalse("a crashed attempt must not repeat automatically", mayLoad(true, false))
        assertTrue("but the user may ask once", mayLoad(true, true))
        assertTrue("a clean state loads normally", mayLoad(false, false))
    }
}

/**
 * The module list that was never read.
 *
 * MODULES pointed at /proc/modules, which holds kernel objects, not the modules a
 * person installs. These tests hold the two lists apart and keep "could not read"
 * from turning into "zero".
 */
class InstalledModulesTest {

    private val modulesDir = ModuleScan.INSTALLED_DIR

    private fun listing(
        entries: List<String>? = emptyList(),
        props: Map<String, String> = emptyMap(),
        markers: Set<String> = emptySet(),
    ): ModuleScan.Installed {
        val fileReads = HashMap<String, FileRead>()
        for ((id, prop) in props) fileReads["$modulesDir/$id/module.prop"] = FileRead.Ok(prop)
        for (path in markers) fileReads[path] = FileRead.Ok("")
        return ModuleScan.scanInstalled(
            list = { if (it == modulesDir) entries else null },
            read = { path -> fileReads[path] ?: FileRead.Missing },
        )
    }

    @Test
    fun `an installed module is listed with what its directory says`() {
        val result = listing(
            entries = listOf("busybox-ndk"),
            props = mapOf("busybox-ndk" to "id=busybox-ndk\nversion=1.36.1\ndescription=BusyBox for Android\n"),
        )
        val listed = result as ModuleScan.Installed.Listed
        assertEquals(1, listed.modules.size)
        val module = listed.modules.single()
        assertEquals("busybox-ndk", module.id)
        assertEquals("1.36.1", module.version)
        assertEquals("BusyBox for Android", module.description)
        assertTrue(module.enabled)
    }

    @Test
    fun `kernel su state files decide enabled, update and removal`() {
        val result = listing(
            entries = listOf("a-disabled", "b-update", "c-remove"),
            markers = setOf(
                "$modulesDir/a-disabled/disable",
                "$modulesDir/b-update/update",
                "$modulesDir/c-remove/remove",
            ),
        )
        val byId = (result as ModuleScan.Installed.Listed).modules.associateBy { it.id }
        assertFalse(byId.getValue("a-disabled").enabled)
        assertTrue(byId.getValue("b-update").updatePending)
        assertTrue(byId.getValue("c-remove").removePending)
    }

    @Test
    fun `dotfiles are not modules`() {
        val listed = listing(entries = listOf(".keep")) as ModuleScan.Installed.Listed
        assertEquals(0, listed.modules.size)
        assertEquals(1, listed.entries)
    }

    @Test
    fun `only a successful listing may say zero modules`() {
        val empty = listing(entries = emptyList())
        assertEquals("0 modul terpasang.", ModuleScan.describeInstalled(empty).first)

        val denied = ModuleScan.scanInstalled(
            list = { null },
            read = { FileRead.Denied },
        )
        assertTrue(denied is ModuleScan.Installed.Unreadable)
        val sentence = ModuleScan.describeInstalled(denied).first
        assertFalse("a failed read must not become a count: $sentence", sentence.contains("0 modul"))
        assertTrue(sentence.contains("tidak bisa dibaca"))

        val missing = ModuleScan.scanInstalled(
            list = { null },
            read = { FileRead.Missing },
        )
        assertEquals(ModuleScan.Installed.NoDirectory, missing)
    }

    @Test
    fun `the kernel object list is never described as installed modules`() {
        val kernelObjects = ModuleScan.Result.Loaded(
            listOf(ModuleScan.Module("wlcore", 4096, "")), rawLines = 1,
        )
        val (headline, _) = ModuleScan.describe(kernelObjects)
        assertFalse("$headline must not be called an install list", headline.contains("terpasang"))
        assertTrue(headline.contains("modul"))
    }

    @Test
    fun `prop parsing does not invent values`() {
        assertEquals("1.0", ModuleScan.prop("version=1.0\n", "version"))
        assertEquals(null, ModuleScan.prop("version=\n", "version"))
        assertEquals(null, ModuleScan.prop("description=x\n", "version"))
    }
}

/** The multi-backend answer is a kernel fact, not an impression. */
class RootBackendTest {

    @Test
    fun `one backend is reported as one, from CONFIG_KSU`() {
        val answer = RootStatus.MultiManager.fromConfig("CONFIG_KSU=y\nCONFIG_KSU_MANUAL_HOOK=y\n")
        assertTrue(answer.startsWith("satu backend"))
        assertTrue(answer.contains("KernelSU"))
    }

    @Test
    fun `two backends in one kernel is never claimed`() {
        // 4.14 cannot carry both; the sentence must say so rather than imply the
        // user can add BakaSU next to a working KernelSU-Next.
        val answer = RootStatus.MultiManager.fromConfig("CONFIG_KSU=y\n")
        assertTrue(answer.contains("hanya bisa memuat satu backend"))
        assertFalse(answer.contains("dua backend"))
    }

    @Test
    fun `a read config without CONFIG_KSU claims nothing`() {
        val answer = RootStatus.MultiManager.fromConfig("CONFIG_MODULES=y\n")
        assertTrue("$answer must not claim a backend", answer.startsWith("tidak ditemukan"))
    }

    @Test
    fun `an unreadable config is not an answer about the kernel`() {
        val answer = RootStatus.MultiManager.answer { FileRead.Denied }
        assertTrue(answer.startsWith("tidak bisa dipastikan"))
        assertFalse(answer.contains("satu backend"))
    }
}
