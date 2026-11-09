package com.rifsxd.ksunext.ui.preflight

import java.io.File
import java.io.IOException
import java.io.RandomAccessFile

/**
 * Bounded ZIP header checks. In particular, BusyBox may use local headers while
 * java.util.zip uses the central directory, so their names and sizes must agree.
 * ZIP64, split archives, encryption and Unix special files are refused; this is
 * deliberately not a full decompression, malware scan or compatibility test.
 */
internal object ZipStructure {
    private const val END = 0x06054b50L
    private const val CENTRAL = 0x02014b50L
    private const val LOCAL = 0x04034b50L
    private const val DESCRIPTOR = 0x08074b50L

    private fun u16(data: ByteArray, offset: Int): Int =
        (data[offset].toInt() and 0xff) or ((data[offset + 1].toInt() and 0xff) shl 8)
    private fun u32(data: ByteArray, offset: Int): Long =
        u16(data, offset).toLong() or (u16(data, offset + 2).toLong() shl 16)
    private fun invalid(): Nothing = throw PreflightException(PreflightProblem.INVALID_ZIP)
    private fun unsupported(): Nothing = throw PreflightException(PreflightProblem.UNSUPPORTED_ZIP)

    fun validate(file: File, maxEntries: Int): Int {
        try {
            RandomAccessFile(file, "r").use { input ->
                val size = input.length()
                if (size < 22) invalid()
                val tailSize = minOf(size, 22L + 65_535L).toInt()
                val tail = ByteArray(tailSize)
                input.seek(size - tailSize)
                input.readFully(tail)
                val eocd = (tailSize - 22 downTo 0).firstOrNull { offset ->
                    u32(tail, offset) == END && offset + 22 + u16(tail, offset + 20) == tailSize
                } ?: invalid()
                val entries = u16(tail, eocd + 10)
                if (entries == 0xffff || u16(tail, eocd + 4) != 0 || u16(tail, eocd + 6) != 0) unsupported()
                if (entries > maxEntries) throw PreflightException(PreflightProblem.TOO_MANY_ENTRIES)
                if (u16(tail, eocd + 8) != entries) invalid()
                val centralSize = u32(tail, eocd + 12)
                val centralOffset = u32(tail, eocd + 16)
                val endOffset = size - tailSize + eocd
                if (centralSize == 0xffffffffL || centralOffset == 0xffffffffL) unsupported()
                if (centralOffset + centralSize != endOffset) invalid()

                val regions = ArrayList<Pair<Long, Long>>(entries)
                var cursor = centralOffset
                repeat(entries) {
                    if (cursor + 46 > endOffset) invalid()
                    input.seek(cursor)
                    val header = ByteArray(46)
                    input.readFully(header)
                    if (u32(header, 0) != CENTRAL) invalid()
                    val flags = u16(header, 8)
                    val method = u16(header, 10)
                    val crc = u32(header, 16)
                    val compressed = u32(header, 20)
                    val uncompressed = u32(header, 24)
                    val nameSize = u16(header, 28)
                    val extraSize = u16(header, 30)
                    val commentSize = u16(header, 32)
                    val disk = u16(header, 34)
                    val localOffset = u32(header, 42)
                    if ((flags and 0x41) != 0 || disk != 0 || compressed == 0xffffffffL ||
                        uncompressed == 0xffffffffL || localOffset == 0xffffffffL) unsupported()
                    if (nameSize == 0 || nameSize > 4096) invalid()
                    val host = header[5].toInt() and 0xff
                    val mode = (u32(header, 38) ushr 16).toInt()
                    val fileType = mode and 0xf000
                    if (host in setOf(3, 19) && fileType !in setOf(0, 0x4000, 0x8000)) {
                        throw PreflightException(PreflightProblem.UNSAFE_PATH)
                    }
                    val next = cursor + 46L + nameSize + extraSize + commentSize
                    if (next > endOffset) invalid()
                    val centralName = ByteArray(nameSize)
                    input.readFully(centralName)
                    if (localOffset + 30 > centralOffset) invalid()
                    input.seek(localOffset)
                    val local = ByteArray(30)
                    input.readFully(local)
                    if (u32(local, 0) != LOCAL || u16(local, 6) != flags || u16(local, 8) != method ||
                        u16(local, 26) != nameSize) invalid()
                    val localExtraSize = u16(local, 28)
                    val dataOffset = localOffset + 30L + nameSize + localExtraSize
                    val dataEnd = dataOffset + compressed
                    if (dataEnd > centralOffset) invalid()
                    val localName = ByteArray(nameSize)
                    input.readFully(localName)
                    if (!centralName.contentEquals(localName)) invalid()
                    var regionEnd = dataEnd
                    if ((flags and 8) == 0) {
                        if (u32(local, 14) != crc || u32(local, 18) != compressed || u32(local, 22) != uncompressed) invalid()
                    } else {
                        if (dataEnd + 12 > centralOffset) invalid()
                        input.seek(dataEnd)
                        val first = ByteArray(4)
                        input.readFully(first)
                        val hasSignature = u32(first, 0) == DESCRIPTOR
                        val descriptorLength = if (hasSignature) 16 else 12
                        if (dataEnd + descriptorLength > centralOffset) invalid()
                        val descriptor = ByteArray(descriptorLength)
                        input.seek(dataEnd)
                        input.readFully(descriptor)
                        val base = if (hasSignature) 4 else 0
                        if (u32(descriptor, base) != crc || u32(descriptor, base + 4) != compressed ||
                            u32(descriptor, base + 8) != uncompressed) invalid()
                        regionEnd += descriptorLength
                    }
                    regions.add(localOffset to regionEnd)
                    cursor = next
                }
                if (cursor != endOffset) invalid()
                val sorted = regions.sortedBy { it.first }
                for (index in 1 until sorted.size) if (sorted[index].first < sorted[index - 1].second) invalid()
                return entries
            }
        } catch (error: PreflightException) {
            throw error
        } catch (_: IOException) {
            throw PreflightException(PreflightProblem.INVALID_ZIP)
        } catch (_: IndexOutOfBoundsException) {
            throw PreflightException(PreflightProblem.INVALID_ZIP)
        }
    }
}
