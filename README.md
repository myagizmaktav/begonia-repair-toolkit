# begonia-repair-toolkit

Redmi Note 8 Pro **begonia** üzerindeki Avrupa ROM ve NV onarım sürecini belgelendiren, özel bir onarım paketini bilgisayarda hazırlayan araç. Kapsam **MIUI EEA V12.5.15.0.RGGEUXM / Android 11** ve **4.14.186** çekirdek ailesidir. Redmi 7 veya başka bir cihaz için değildir.

Araç yalnız bu telefona ait özgün IMEI değerlerini geri yükleme hazırlığı içindir. IMEI üretmez, başka cihazdan kimlik kopyalamaz ve Türkiye kayıt işlemi yapmaz. Telefonun kayıt durumu yazılım hazırlama ile değişmez. Hiçbir komut ADB, fastboot veya USB üzerinden telefona erişmez.

## Bu vakada ne bulundu?

- Avrupa ROM kuruldu. İncelenen NVRAM bölümü tamamen sıfırdı; başlangıç yedeği bu durumu koruyordu, sağlam fabrika kalibrasyon yedeği değildi.
- Dört dosyada yanlış SELinux etiketi bulundu: `nvdata/fstab.mt6785`, `nvdata/md/NVRAM/NVD_CORE/MTCR_000`, `nvdata/media/Audio_ver1_Vol_custom`, `protect_s/md/NA77_006`.
- İçerik hashleri değişmeden stok etiketleri uygulandı. Sonraki recovery kaydındaki `--show_bad_nv`, NV doğrulamasının açılışı durdurduğunu gösterdi. Etiket düzeltmesi tek başına özgün NV içeriğini geri getirmez.
- Doğrulanmış bölüm yedekleri, pinli kaynaklar ve ayrıca kontrol edilen yazma adımları kullanılarak Android yeniden açıldı. Kullanıcı **arama ve mobil verinin çalıştığını doğruladı**. YouTube/hoparlör sesi sorununun teşhisi henüz tamamlanmadı; cihazın bütün işlevlerinin sağlıklı olduğu iddia edilmiyor.

Bu bulgular tek cihazlık vaka kaydıdır. Aynı belirti her cihazda aynı nedenle oluşmaz. Depoda bu cihaza ait kimlik, günlük, yedek veya firmware bulunmaz.

## Üç komut

Python 3.9+ yeterlidir. `build` ayrıca güvendiğiniz bir PHP CLI, OpenSSL, ZipArchive ve little-endian PHP ortamı gerektirir. `prepare` kaynakları indirir; `build` pinli upstream PHP kodunu bilgisayarda çalıştırır. PHP kurulumu bu aracın kapsamında değildir.

Özel yapılandırmayı temp altında oluşturun:

```sh
TASK_WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/begonia-private.XXXXXX")"
PRIVATE_ENV="$TASK_WORKDIR/device.env"
cp .env.example "$PRIVATE_ENV"
chmod 600 "$PRIVATE_ENV"
```

`PRIVATE_ENV` dosyasını yerel editörünüzde doldurun. IMEI'leri terminal komutuna, ekran görüntüsüne, issue'ya veya README'ye yazmayın. Yalnız bu cihazın kendi özgün IMEI'lerini ve doğrulanmış kendi chip/MAC bilgilerini kullanın. Bilinmeyen bir alanı başka telefondan veya internetten alınan değerle doldurmayın. Araç eksik kimlik ya da MAC üretmez. MAC kontrolü yalnız sıfır olmayan unicast biçimini doğrular; adresin fabrikadaki değer veya cihaza ait olduğunu kanıtlamaz.

```sh
# Varsayılan da validate'dir: indirme veya PHP çalıştırma yok.
python3 repair_builder.py validate --env-file "$PRIVATE_ENV"

# Yalnız pinli kaynakları temp'e indirir ve hashlerini doğrular; çalıştırmaz.
python3 repair_builder.py prepare --runtime-dir "$TASK_WORKDIR/runtime"

# Verilen PHP ile pinli upstream kodunu çalıştırır; telefona erişmez.
python3 repair_builder.py build --env-file "$PRIVATE_ENV" \
  --runtime-dir "$TASK_WORKDIR/runtime" --php /absolute/path/to/php
```

FrankenPHP için aynı build çağrısı:

```sh
python3 repair_builder.py build --env-file "$PRIVATE_ENV" \
  --runtime-dir "$TASK_WORKDIR/runtime" \
  --php /absolute/path/to/frankenphp --php-mode frankenphp
```

Yardımcı `php-cli` alt komutunu kendisi ekler. `--php` değerine güvendiğiniz çalıştırılabilir dosyanın mutlak yolunu verin.

Yapılandırma `KEY=VALUE` metnidir; shell gibi yorumlanmaz. `export`, değişken genişletmesi, komut çalıştırma, kaçış dizileri ve satır sonu yorumları desteklenmez. Dosya size ait olmalı ve POSIX izinleri `600` olmalıdır. Hata mesajları alan değerlerini, upstream stdout/stderr'ini veya özel dosya yolunu yazdırmaz.

## Çıktı ve sınırlar

Çıktı `$TASK_WORKDIR/runtime/private-output-*/begonia-repair-review.zip` altındadır. **Bu dosya cihaz kimliklerini içerir; özel kalmalıdır ve doğrudan recovery ile flash edilemez.** Yalnız `nvram.img`, `nvdata.img`, vendor modülü, init dosyası ve özel hash manifesti içerir. Upstream installer giriş noktaları ve diğer executable yardımcıları dışarıda bırakılır. Geçici özgün flashable ZIP ve `config.txt` build sonunda kaldırılır.

Kontroller; IMEI biçimi/Luhn, chip ve MAC biçimi, sabit kaynak boyutları/SHA-256, ZIP CRC, NVRAM TOC sınırları ve genel checksum, CSSD checksum/TLV içindeki iki IMEI+chip+MAC eşleşmesi, Wi-Fi/BT kayıtları ve checksum'ları ile modül/init/NVDATA kaynak eşleşmesini kapsar. Bunlar sahiplik, operatör kaydı, fabrikadaki kalibrasyon veya RF kalitesi kanıtı değildir. Şablon özgün kalibrasyonları geri getirmez.

Pinli modülün vermagic'i `4.14.186-g215472d`; vakadaki stok kernel `4.14.186-g4e5507d5edae` idi. Sürüm ön ekinin aynı olması ABI uyumluluğu garantisi değildir. Upstream init, normal yüklemeyi ve ardından zorlamalı yüklemeyi dener; normal yükleme başarılıysa ikinci denemenin “already exists” sonucu tek başına hata sayılmaz. Yükleme ve modem sonucu ayrıca doğrulanmalıdır.

## Telefonda uygulama

Otomatik kurulum yoktur. İnceleme paketi hazırlanmış olsa bile yazma işlemleri ayrı bir karardır. **Bootloader açık kalmalıdır; relock yapılmaz.** Gerçek bölüm adları, mount noktaları, yedek geri dönüşü ve vendor doğrulaması kontrol edilmeden payload yazılmamalıdır. Vakada kullanılan somut kontrollü sıra [recovery uygulama notlarında](docs/recovery-checklist.md) bulunur. Bu notlar kimlik veya cihaz seri numarası içermez.

Upstream installer'ı doğrudan dağıtmama nedeni: `/nvdata` sabit mount noktası gerçek `/mnt/vendor/nvdata` ile uyuşmayabilir; vendor yazma sonuçları assert edilmez; recovery shell'inde `standalone` algılanırsa Magisk bulunmayan akış yazmadan başarı dönebilir. `run_program(...) && ...` edify'de shell'deki başarı testi değildir. İnceleme paketi bu installer'ı içermez.

## Gizlilik ve test

`.gitignore` özel env, config, yedek, firmware, binary ve logları dışlar. Bu tek başına güvenlik sınırı değildir: yanlışlıkla izlemeye alınmış dosyayı temizlemez. Yayın öncesi staged dosyalar ayrıca kontrol edilmelidir. Hashler ve üretilen paketler de cihazla ilişkilendirilebilir; bunları issue veya release'e eklemeyin. Temp dosyalarının sonradan silinmesi güvenli disk silme garantisi değildir. Kullanılacak geri dönüş yedeklerini işlem ve donanım testleri tamamlanmadan silmeyin.

```sh
python3 -m unittest discover -s tests -v
git diff --cached --stat
git diff --cached --check
```

Testler sentetik değerler kullanır, telefona erişmez ve ağ/PHP gerektirmez. Tam build doğrulaması için gerekli PHP ve pinli önbellek ayrıca sağlanır. Kaynak ve lisans bilgileri [THIRD_PARTY.md](THIRD_PARTY.md) ve [LICENSE](LICENSE) içindedir.

Doğrulanan ROM/recovery indirme kaynakları ve çalışma ortamı [kaynaklar sayfasında](docs/sources.md) bulunur.
