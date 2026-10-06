package app.vitapulse.android.feature.wellbeing.domain

import org.junit.Assert.assertEquals
import org.junit.Test

class WellbeingTrendAnalyzerTest {
    @Test
    fun requiresAtLeastThreeRecordedObservations() {
        assertEquals("INSUFFICIENT_DATA", WellbeingTrendAnalyzer.classify(listOf(4.0)).classification)
    }

    @Test
    fun classifiesStableAndImprovingSeriesFromRecordedValues() {
        assertEquals("STABLE", WellbeingTrendAnalyzer.classify(listOf(3.0, 3.1, 3.0, 3.1, 3.0)).classification)
        assertEquals("IMPROVING", WellbeingTrendAnalyzer.classify(listOf(1.0, 1.5, 2.0, 4.0, 4.5, 5.0)).classification)
    }

    @Test
    fun preservesVariableHistoryInsteadOfAttributingItsCause() {
        val trend = WellbeingTrendAnalyzer.classify(listOf(1.0, 5.0, 1.0, 5.0, 1.0, 5.0))
        assertEquals("VARIABLE", trend.classification)
        assertEquals(6, trend.observationCount)
    }
}
