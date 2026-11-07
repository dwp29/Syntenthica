package com.rifsxd.ksunext.ui.theme

import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.material3.Shapes
import androidx.compose.ui.unit.dp

// Small squared-off corners echo a pixel grid without shrinking touch targets.
val GlassShapes = Shapes(
    extraSmall = CutCornerShape(2.dp),
    small = CutCornerShape(3.dp),
    medium = CutCornerShape(4.dp),
    large = CutCornerShape(5.dp),
    extraLarge = CutCornerShape(7.dp),
)
