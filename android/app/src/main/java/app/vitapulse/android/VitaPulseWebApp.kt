package app.vitapulse.android

import android.content.Intent
import android.net.Uri
import android.view.View
import android.webkit.CookieManager
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import java.net.URI
import java.net.URISyntaxException

@Composable
internal fun VitaPulseWebApp(
    url: String,
    visible: Boolean,
    modifier: Modifier = Modifier,
    onWebViewCreated: (WebView) -> Unit,
    onCanGoBackChange: (Boolean) -> Unit,
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    var loading by remember { mutableStateOf(true) }
    var loadFailed by remember { mutableStateOf(false) }
    val webView = remember(context, url) {
        WebView(context).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.allowFileAccess = false
            settings.allowContentAccess = false
            settings.mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            settings.javaScriptCanOpenWindowsAutomatically = false
            settings.setSupportMultipleWindows(false)
            setBackgroundColor(android.graphics.Color.rgb(246, 248, 247))
            isVerticalScrollBarEnabled = false
            CookieManager.getInstance().setAcceptCookie(true)
            CookieManager.getInstance().setAcceptThirdPartyCookies(this, false)
            webChromeClient = WebChromeClient()
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                    val target = request.url
                    if (isSameOriginWebUrl(target.toString(), url)) return false
                    if (target.scheme == "https" || target.scheme == "mailto" || target.scheme == "tel") {
                        context.startActivity(Intent(Intent.ACTION_VIEW, target))
                    }
                    return true
                }

                override fun onPageStarted(view: WebView, pageUrl: String?, favicon: android.graphics.Bitmap?) {
                    loading = true
                    loadFailed = false
                }

                override fun onPageFinished(view: WebView, pageUrl: String?) {
                    loading = false
                    onCanGoBackChange(view.canGoBack())
                }

                override fun doUpdateVisitedHistory(view: WebView, visitedUrl: String?, isReload: Boolean) {
                    onCanGoBackChange(view.canGoBack())
                }

                override fun onReceivedError(
                    view: WebView,
                    request: WebResourceRequest,
                    error: android.webkit.WebResourceError,
                ) {
                    if (request.isForMainFrame) {
                        loading = false
                        loadFailed = true
                    }
                }
            }
            loadUrl(url)
        }
    }
    onWebViewCreated(webView)

    DisposableEffect(lifecycleOwner, webView) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_RESUME -> webView.onResume()
                Lifecycle.Event.ON_PAUSE -> webView.onPause()
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            webView.stopLoading()
            webView.destroy()
        }
    }

    Box(modifier) {
        AndroidView(
            factory = { webView },
            modifier = Modifier.fillMaxSize(),
            update = { view ->
                view.visibility = if (visible) View.VISIBLE else View.INVISIBLE
                if (view.url.isNullOrBlank()) view.loadUrl(url)
            },
        )
        if (visible && loading && !loadFailed) {
            Box(
                Modifier.fillMaxSize().background(Color(0xFFF6F8F7)),
                contentAlignment = Alignment.Center,
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    CircularProgressIndicator(color = Color(0xFF237A6B))
                    Text("Opening VitaPulse…", color = Color(0xFF34443F))
                }
            }
        }
        if (visible && loadFailed) {
            Column(
                Modifier.fillMaxSize().background(Color(0xFFF6F8F7)).padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                Text("VitaPulse could not be reached.", style = MaterialTheme.typography.titleMedium)
                Text(
                    "Check your internet connection, then try again.",
                    modifier = Modifier.padding(top = 8.dp),
                    color = Color(0xFF53635E),
                )
                Button(
                    onClick = {
                        loading = true
                        loadFailed = false
                        webView.reload()
                    },
                    modifier = Modifier.padding(top = 16.dp),
                ) {
                    Text("Try again")
                }
            }
        }
    }
}

internal fun isSameOriginWebUrl(candidateUrl: String, appUrl: String): Boolean {
    val candidate = try {
        URI(candidateUrl)
    } catch (_: URISyntaxException) {
        return false
    }
    val app = try {
        URI(appUrl)
    } catch (_: URISyntaxException) {
        return false
    }
    if (candidate.userInfo != null || app.userInfo != null) return false
    if (!candidate.scheme.equals(app.scheme, ignoreCase = true)) return false
    val candidateHost = candidate.host ?: return false
    val appHost = app.host ?: return false
    if (!candidateHost.equals(appHost, ignoreCase = true)) return false
    return effectivePort(candidate) == effectivePort(app)
}

private fun effectivePort(uri: URI): Int =
    if (uri.port >= 0) uri.port else if (uri.scheme.equals("https", ignoreCase = true)) 443 else 80
