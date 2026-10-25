# Kullanılan kaynaklar

Dosyalar bu depoda yeniden dağıtılmaz. Hedef model ve sürüm eşleşmesi doğrulanmadan başka cihazda kullanılmamalıdır.

| Bileşen | Kaynak ve doğrulama |
| --- | --- |
| Android platform-tools | [Google Android SDK Platform-Tools](https://developer.android.com/tools/releases/platform-tools) |
| Resmî EEA ROM | [Xiaomi V12.5.15.0.RGGEUXM fastboot arşivi](https://bn.d.miui.com/V12.5.15.0.RGGEUXM/begonia_eea_global_images_V12.5.15.0.RGGEUXM_20220826.0000.00_11.0_eea_b8c6b15c15.tgz), MD5 `b8c6b15c15bb5edf8ce68e0393d2ae84` |
| BRP recovery | [santoshhh000 MIUI12.5 dağıtım klasörü](https://sourceforge.net/projects/begonianon-cfw/files/fastboot-zip/MIUI12.5/), `BRP3.5.2v3.1-fastboot.zip` SHA256 `2914e6c0b6c8b15631097cbb09716a2b08926a33dd879549d2961fb19f93737f`; içindeki recovery imajı SHA256 `a6a4ef8baa0c87c50cc6cdb6c693b2c4a38015cfe79f6180d7baae3fcf00b512` |
| NV hazırlama kaynakları | [Pinli upstream commit](https://github.com/timjosten/mtk_imei/tree/100e67c2696f6247fef398cf5b46b9cb260e0f93); bütün dosya boyutları/SHA256 değerleri `upstream-manifest.json` içinde |
| Kullanılan macOS PHP ortamı | [FrankenPHP v1.13.3](https://github.com/php/frankenphp/releases/tag/v1.13.3), `frankenphp-mac-arm64` SHA256 `f6acd5a97f46ff13f362329d1669012026c9a35cf00f3a8368b12ec7010cd926` |
| Hoparlör tanılama | [Xiaomi resmî CIT hoparlör test bilgisi](https://www.mi.com/ph/support/faq/details/KA-639826/) |

ROM Android 11 tabanlıdır ve güvenlik yaması 2022-07-01 tarihindedir. Bu kayıt, güncel güvenlik desteği veya her cihazda uyumluluk iddiası değildir. MD5 burada arşiv bütünlüğü için yayımlanan eşleşme bilgisidir; tek başına güvenilir kaynak kanıtı olarak kullanılmaz.

Vakadaki doğrulama: 14 yerel unit test geçti. macOS arm64 FrankenPHP ile uçtan uca paket hazırlama çalıştı; üretilen dört payload başarılı şebeke onarımında kullanılan dosyalarla birebir eşleşti. Bu testte kullanılan özel kimlikler ve kişiselleştirilmiş hashler depoya eklenmedi. Modül `/proc/modules` listesinde yerleşik görünmedi; bu nedenle modülün yüklenme durumuna ilişkin ayrı bir kesinlik iddia edilmiyor. İşlevsel sonuç, kimlik eşleşmesi ve kullanıcının arama/veri testiyle doğrulandı. Hoparlör incelemesi devam ediyor.
