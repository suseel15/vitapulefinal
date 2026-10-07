package app.vitapulse.android

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class VitaPulseWebUrlPolicyTest {
    private val appUrl = "https://vitapulse-eosin.vercel.app/"

    @Test
    fun allowsPagesAndAssetsOnTheConfiguredOrigin() {
        assertTrue(isSameOriginWebUrl("https://vitapulse-eosin.vercel.app/#wellbeing", appUrl))
        assertTrue(isSameOriginWebUrl("https://vitapulse-eosin.vercel.app/src/ui.js", appUrl))
    }

    @Test
    fun rejectsDifferentHostsSchemesAndPorts() {
        assertFalse(isSameOriginWebUrl("https://example.com/", appUrl))
        assertFalse(isSameOriginWebUrl("http://vitapulse-eosin.vercel.app/", appUrl))
        assertFalse(isSameOriginWebUrl("https://vitapulse-eosin.vercel.app:8443/", appUrl))
    }

    @Test
    fun rejectsMalformedAndCredentialBearingUrls() {
        assertFalse(isSameOriginWebUrl("not a URL", appUrl))
        assertFalse(isSameOriginWebUrl("https://user@vitapulse-eosin.vercel.app/", appUrl))
        assertFalse(isSameOriginWebUrl("https://vitapulse-eosin.vercel.app/", "not a URL"))
    }
}
