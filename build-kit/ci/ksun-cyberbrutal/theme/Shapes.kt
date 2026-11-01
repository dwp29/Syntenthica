package com.rifsxd.ksunext.ui.theme

import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.material3.Shapes
import androidx.compose.ui.unit.dp

// Synthetica 2.1 — Cyberbrutalist 45-degree chamfered industrial geometry.
// Asymmetric top-end & bottom-start cuts create unmistakable brutalist plates.
val KernelSUThemeShapes = Shapes(
    extraSmall = CutCornerShape(topStart = 0.dp, topEnd = 5.dp, bottomEnd = 0.dp, bottomStart = 5.dp),
    small = CutCornerShape(topStart = 0.dp, topEnd = 8.dp, bottomEnd = 0.dp, bottomStart = 8.dp),
    medium = CutCornerShape(topStart = 0.dp, topEnd = 14.dp, bottomEnd = 0.dp, bottomStart = 14.dp),
    large = CutCornerShape(topStart = 0.dp, topEnd = 18.dp, bottomEnd = 0.dp, bottomStart = 18.dp),
    extraLarge = CutCornerShape(topStart = 0.dp, topEnd = 22.dp, bottomEnd = 0.dp, bottomStart = 22.dp),
)
