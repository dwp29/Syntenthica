package net.pure.manager.media

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The playback arithmetic, pinned.
 *
 * A media player is mostly a clock, and a clock is where the bugs are: a seek bar
 * that jumps backwards under the thumb, a "previous" that skips two tracks, a
 * duration that has not arrived yet rendering as `-1:59`. None of that needs a phone
 * to be wrong, so all of it is plain functions with tests.
 */
class MediaTest {

    // ------------------------------------------------------------------ clock

    @Test
    fun clockFormatsMinutesAndSeconds() {
        assertEquals("0:00", formatClock(0))
        assertEquals("0:07", formatClock(7_000))
        assertEquals("1:05", formatClock(65_000))
        assertEquals("9:59", formatClock(599_000))
    }

    @Test
    fun clockGrowsAnHourFieldOnlyWhenNeeded() {
        assertEquals("1:00:00", formatClock(3_600_000))
        assertEquals("2:03:04", formatClock(7_384_000))
    }

    /** A player that has not prepared yet reports -1; showing `-1:-1` looks broken. */
    @Test
    fun anUnknownDurationIsNotANegativeClock() {
        assertEquals("--:--", formatClock(-1))
        assertEquals("--:--", formatClock(Long.MAX_VALUE))
    }

    /** Truncation, not rounding: 999 ms is still the first second. */
    @Test
    fun millisecondsRoundDown() {
        assertEquals("0:00", formatClock(999))
        assertEquals("0:01", formatClock(1_000))
    }

    // ------------------------------------------------------------------- seek

    /**
     * While the thumb is down, the drag wins.
     *
     * The player keeps reporting its pre-seek position for a frame or two after a
     * seek; a bar that trusts every update springs backwards out from under the
     * finger. This is the rule that stops it.
     */
    @Test
    fun aDragOverridesThePlayerPosition() {
        assertEquals(30_000, shownPosition(positionMs = 5_000, dragPositionMs = 30_000f.toLong(), durationMs = 60_000))
    }

    @Test
    fun releasingTheThumbReturnsToThePlayerPosition() {
        assertEquals(5_000, shownPosition(positionMs = 5_000, dragPositionMs = null, durationMs = 60_000))
    }

    @Test
    fun theShownPositionNeverExceedsTheDuration() {
        assertEquals(60_000, shownPosition(90_000, null, 60_000))
        assertEquals(0, shownPosition(-5_000, null, 60_000))
    }

    @Test
    fun anUnknownDurationPinsTheBarAtZero() {
        assertEquals(0, shownPosition(12_000, null, -1))
    }

    @Test
    fun progressIsZeroRatherThanNaNWithoutADuration() {
        assertEquals(0f, progressFraction(1_000, -1))
        assertEquals(0f, progressFraction(1_000, 0))
    }

    @Test
    fun progressIsAFractionAndCannotOvershoot() {
        assertEquals(0.5f, progressFraction(30_000, 60_000))
        assertEquals(1f, progressFraction(90_000, 60_000))
        assertEquals(0f, progressFraction(-1, 60_000))
    }

    // --------------------------------------------------------------- playlist

    @Test
    fun nextGoesToTheFollowingTrack() {
        assertEquals(2, nextIndex(current = 1, count = 4, repeat = false, shuffle = false))
    }

    /** Without repeat the last track stays last; stopping on silence is worse. */
    @Test
    fun nextAtTheEndStaysPutWithoutRepeat() {
        assertEquals(3, nextIndex(current = 3, count = 4, repeat = false, shuffle = false))
    }

    @Test
    fun nextAtTheEndWrapsWithRepeat() {
        assertEquals(0, nextIndex(current = 3, count = 4, repeat = true, shuffle = false))
    }

    @Test
    fun previousGoesBack() {
        assertEquals(0, previousIndex(current = 1, count = 4, repeat = false, shuffle = false))
    }

    @Test
    fun previousAtTheStartStaysPutWithoutRepeat() {
        assertEquals(0, previousIndex(current = 0, count = 4, repeat = false, shuffle = false))
    }

    @Test
    fun previousAtTheStartWrapsWithRepeat() {
        assertEquals(3, previousIndex(current = 0, count = 4, repeat = true, shuffle = false))
    }

    /**
     * Shuffle must never pick the track that is already playing. With three tracks
     * there are only two valid answers, and a naive `random` picks the current one a
     * third of the time -- which reads as the button doing nothing.
     */
    @Test
    fun shuffleNeverPicksTheCurrentTrack() {
        val count = 5
        for (current in 0 until count) {
            for (seed in 0 until count) {
                assertTrue(nextIndex(current, count, repeat = false, shuffle = true, seed = seed) != current)
                assertTrue(previousIndex(current, count, repeat = false, shuffle = true, seed = seed) != current)
            }
        }
    }

    @Test
    fun shuffleStaysInsideThePlaylist() {
        for (current in 0 until 6) {
            for (seed in 0 until 10) {
                val n = nextIndex(current, 6, false, true, seed)
                val p = previousIndex(current, 6, false, true, seed)
                assertTrue(n in 0 until 6)
                assertTrue(p in 0 until 6)
            }
        }
    }

    /** A one-track playlist repeats that track; refusing to play it is absurd. */
    @Test
    fun aSingleTrackPlaysItself() {
        assertEquals(0, nextIndex(0, 1, repeat = false, shuffle = true))
        assertEquals(0, previousIndex(0, 1, repeat = false, shuffle = false))
    }

    // ------------------------------------------------------------- prev or not

    @Test
    fun previousWithinThreeSecondsGoesToThePreviousTrack() {
        assertFalse(previousRestartsInsteadOfGoingBack(0))
        assertFalse(previousRestartsInsteadOfGoingBack(2_999))
    }

    @Test
    fun previousAfterThreeSecondsRestartsTheTrack() {
        assertTrue(previousRestartsInsteadOfGoingBack(3_001))
    }

    // -------------------------------------------------------------- file types

    @Test
    fun mediaKindsAreRecognisedFromTheExtension() {
        assertEquals(MediaKind.IMAGE, MediaKind.of("jpg"))
        assertEquals(MediaKind.IMAGE, MediaKind.of("HEIC"))
        assertEquals(MediaKind.AUDIO, MediaKind.of("mp3"))
        assertEquals(MediaKind.AUDIO, MediaKind.of("flac"))
        assertEquals(MediaKind.VIDEO, MediaKind.of("mp4"))
        assertNull(MediaKind.of("pdf"))
        assertNull(MediaKind.of("txt"))
    }

    @Test
    fun onlyAudioAndVideoAreOfferedToThePlayer() {
        assertTrue(MediaKind.playable("mp3"))
        assertTrue(MediaKind.playable("mkv"))
        assertFalse(MediaKind.playable("jpg"))
        assertFalse(MediaKind.playable("pdf"))
    }

    @Test
    fun theTitleDropsTheExtensionButKeepsTheRestOfTheName() {
        assertEquals("lagu favorit", titleOf("lagu favorit.mp3"))
        // A dotfile has no extension to drop.
        assertEquals(".nomedia", titleOf(".nomedia"))
        assertEquals("no-extension", titleOf("no-extension"))
    }

    @Test
    fun thePlaylistStartsAtTheTappedFile() {
        val paths = listOf("/a/1.mp3", "/a/2.mp3", "/a/3.mp3")
        assertEquals(1, playlistPosition(paths, "/a/2.mp3"))
        // A file that is not in the list still has to open rather than crash.
        assertEquals(0, playlistPosition(paths, "/a/elsewhere.mp3"))
    }

    // -------------------------------------------------------------------- zoom

    @Test
    fun zoomIsClampedToTheAllowedRange() {
        val tooFar = clampZoom(ZoomState(scale = 99f), 1000f, 1000f)
        assertEquals(8f, tooFar.scale)
        val tooSmall = clampZoom(ZoomState(scale = 0.1f), 1000f, 1000f)
        assertEquals(1f, tooSmall.scale)
    }

    /**
     * At fit scale there is no overflow, so any pan snaps back to the centre.
     *
     * The first version clamped to zero unconditionally -- which is the same thing at
     * scale 1 and made panning dead at every other scale.
     */
    @Test
    fun panningIsPinnedAtFitScale() {
        val z = clampZoom(ZoomState(scale = 1f, offsetX = 500f, offsetY = -400f), 1000f, 1000f)
        assertEquals(0f, z.offsetX)
        assertEquals(0f, z.offsetY)
    }

    @Test
    fun panningIsAllowedUpToHalfTheOverflow() {
        // At scale 3 on a 1000 px viewport the overflow is 2000 px, so 1000 px each way.
        val z = clampZoom(ZoomState(scale = 3f, offsetX = 5_000f, offsetY = -5_000f), 1000f, 1000f)
        assertEquals(1_000f, z.offsetX)
        assertEquals(-1_000f, z.offsetY)
    }

    @Test
    fun aDoubleTapTogglesBetweenFitAndTwoAndAHalf() {
        assertEquals(2.5f, doubleTapZoomState(1f))
        assertEquals(1f, doubleTapZoomState(2.5f))
        // Any zoomed-in state returns to fit, so the gesture always has a reset.
        assertEquals(1f, doubleTapZoomState(1.7f))
    }
}
