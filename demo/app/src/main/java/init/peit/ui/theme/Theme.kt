package init.peit.ui.theme

import android.app.Activity
import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext

private val DarkColorScheme = darkColorScheme(
    primary = PeitDarkTeal,
    onPrimary = PeitInk,
    primaryContainer = Color(0xFF174A47),
    onPrimaryContainer = PeitDarkText,
    secondary = Color(0xFFB6C9C7),
    onSecondary = PeitInk,
    tertiary = PeitAmber,
    onTertiary = PeitInk,
    background = PeitDarkCanvas,
    onBackground = PeitDarkText,
    surface = PeitDarkCanvas,
    onSurface = PeitDarkText,
    surfaceVariant = PeitDarkSurface,
    onSurfaceVariant = Color(0xFFB5C6C4),
    error = Color(0xFFFFB4AB),
    onError = Color(0xFF690005)
)

private val LightColorScheme = lightColorScheme(
    primary = PeitTeal,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFD5EFEB),
    onPrimaryContainer = PeitInk,
    secondary = PeitMuted,
    onSecondary = Color.White,
    tertiary = PeitAmber,
    onTertiary = PeitInk,
    background = PeitCanvas,
    onBackground = PeitInk,
    surface = Color.White,
    onSurface = PeitInk,
    surfaceVariant = Color(0xFFE7EFED),
    onSurfaceVariant = PeitMuted,
    error = Color(0xFFB3261E),
    onError = Color.White
)

@Composable
fun PEITTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = false,
    content: @Composable () -> Unit
) {
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }

        darkTheme -> DarkColorScheme
        else -> LightColorScheme
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content
    )
}