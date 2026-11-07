package com.rifsxd.ksunext.ui.theme

import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.material3.Shapes
import androidx.compose.ui.unit.dp

// Angular, but generous enough for touch targets and long localized labels.
val GlassShapes = Shapes(
    extraSmall = CutCornerShape(topStart = 3.dp, topEnd = 5.dp, bottomEnd = 3.dp, bottomStart = 5.dp),
    small = CutCornerShape(topStart = 4.dp, topEnd = 8.dp, bottomEnd = 4.dp, bottomStart = 8.dp),
    medium = CutCornerShape(topStart = 4.dp, topEnd = 12.dp, bottomEnd = 4.dp, bottomStart = 12.dp),
    large = CutCornerShape(topStart = 5.dp, topEnd = 16.dp, bottomEnd = 5.dp, bottomStart = 16.dp),
    extraLarge = CutCornerShape(topStart = 6.dp, topEnd = 20.dp, bottomEnd = 6.dp, bottomStart = 20.dp),
)
