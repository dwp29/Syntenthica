package org.syntenthica.musicrouter;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.os.Bundle;
import android.widget.Toast;

/** A narrow, non-privileged MUSIC_PLAYER bridge to the unmodified SpatialFlow app. */
public final class MusicPlayerRouter extends Activity {
    private static final String MUSIC_PLAYER = "android.intent.action.MUSIC_PLAYER";
    private static final String SPATIALFLOW_PACKAGE = "com.codetrio.spatialflow";
    private static final String SPATIALFLOW_ACTIVITY = "com.codetrio.spatialflow.MainActivity";

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        Intent incoming = getIntent();
        if (incoming == null || !MUSIC_PLAYER.equals(incoming.getAction())) {
            finish();
            return;
        }
        Intent launch = new Intent(Intent.ACTION_MAIN)
                .addCategory(Intent.CATEGORY_DEFAULT)
                .setClassName(SPATIALFLOW_PACKAGE, SPATIALFLOW_ACTIVITY);
        try {
            startActivity(launch);
        } catch (ActivityNotFoundException | SecurityException unavailable) {
            Toast.makeText(this, "SpatialFlow tidak tersedia", Toast.LENGTH_SHORT).show();
        } finally {
            finish();
        }
    }
}
