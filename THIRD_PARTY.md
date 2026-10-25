# Kaynak ve lisans bilgileri

Bu depodaki Python yardımcıları ve belgeler **GPL-3.0-only** altında sunulur. Lisans metni [LICENSE](LICENSE) dosyasındadır.

Paket üreticisi [timjosten/mtk_imei](https://github.com/timjosten/mtk_imei) projesinden gelir. Pinli commit: [`100e67c2696f6247fef398cf5b46b9cb260e0f93`](https://github.com/timjosten/mtk_imei/tree/100e67c2696f6247fef398cf5b46b9cb260e0f93). Upstream lisansı GNU GPL v3'tür. Hazırlama sırasında upstream `LICENSE` ve `README.md` dosyaları da alınır; bildirimleri özel kaynak önbelleğinde korunur.

[upstream-manifest.json](upstream-manifest.json) yalnız kaynak URL'lerini, dosya boyutlarını ve SHA-256 değerlerini içerir. Bu depo ROM, NVRAM şablonu, kernel modülü, upstream PHP dosyası, RSA anahtar dosyası veya cihaza ait yedek dağıtmaz. `prepare` bunları pinli kaynaktan, depo dışındaki özel temp önbelleğine indirir. Upstream'de yayımlanmış RSA imzalama anahtarları üreticinin bu cihaza verdiği özgün sertifika değildir; müşteri anahtarları bu depoya eklenmez.

Python'daki TOC/CSSD/checksum kontrolleri pinli dosya biçiminin ayrı bir doğrulama uygulamasıdır. Kernel modülünün kaynak kodu bu depoda bulunmaz; hash sabitlemesi onun davranışını, ABI uyumluluğunu veya üretici onayını kanıtlamaz.

Üretilen inceleme paketi özel cihaz bilgileri içerir ve yayımlanmamalıdır. Bir upstream bileşenini ayrıca dağıtmak, ilgili lisans ve kaynak kod sunma koşullarını ayrıca değerlendirmeyi gerektirir.

Bu proje Xiaomi, MediaTek, BRP, FrankenPHP veya timjosten tarafından desteklenmiş ya da onaylanmış değildir. PHP/FrankenPHP çalışma ortamı kullanıcı tarafından ayrıca sağlanır; bu depo bu programların binary dosyalarını dağıtmaz.
