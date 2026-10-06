package app.vitapulse.android.core.device

import android.net.Network
import com.google.gson.Gson
import java.net.InetAddress
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.net.SocketTimeoutException
import java.net.URL
import java.util.concurrent.TimeUnit

class Esp32Repository(
    private val baseUrl: String,
) {
    fun api(network: Network): Esp32Api {
        val host = URL(baseUrl).host
        val client = OkHttpClient.Builder()
            .socketFactory(network.socketFactory)
            .dns(object : okhttp3.Dns {
                override fun lookup(hostname: String): List<InetAddress> =
                    network.getAllByName(hostname).toList()
            })
            .connectTimeout(2, TimeUnit.SECONDS)
            .readTimeout(2, TimeUnit.SECONDS)
            .writeTimeout(2, TimeUnit.SECONDS)
            .callTimeout(3, TimeUnit.SECONDS)
            .build()
        return Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create(Gson()))
            .build()
            .create(Esp32Api::class.java)
    }

    fun errorType(error: Throwable): String = when (error) {
        is SocketTimeoutException -> "Request timed out."
        else -> error.message ?: "The ESP32 did not respond."
    }
}
