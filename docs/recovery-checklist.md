# Recovery uygulama kaydı ve geri dönüş

Bu adımlar **begonia / stok EEA V12.5.15.0.RGGEUXM** vakasındaki kontrollü uygulama sırasını açıklar. CLI aracı bunları çalıştırmaz. Örneklerdeki değişkenleri kendi özel çalışma alanınızda hazırlayın; seri numarası ve dosya yollarını depoya kaydetmeyin. Her yazma adımı kullanıcı tarafından ayrıca başlatılır. Başka bir modele uyarlamak için yalnız isim değiştirmek yeterli değildir.

## 1. Başlangıç, recovery ve geri dönüş

- Bootloader açık; ürün adı ve Android/kernel sürümü doğrulanmış olmalı. Bu vakada BRP **3.5.2 v3.1 MIUI 12.5 / Android 11 non-CFW** ile root recovery ADB elde edildi. Android 9 tabanlı bir recovery aynı hedef değildir.
- Mevcut `boot`, `vbmeta`, `recovery` ve NV bölümlerinin geri dönüş kaynakları belirlenir. Stock firmware dosyaları bu depoda dağıtılmaz. Recovery ve vbmeta işlemleri NV içeriği onarımıyla aynı işlem değildir.
- NV için `nvram`, `nvdata`, `nvcfg`, `protect1`, `protect2`, `persist` yedeklenir. Gerçek bölüm cihazları symlink çözümlenerek ve boyutları okunarak kontrol edilir. Yedek dosya boyutu ve SHA-256, cihazdan tekrar okunan bölümle karşılaştırılır. Sıfırlardan oluşan bir bölüm de yedeklenir; bu bir sağlam kalibrasyon yedeği sayılmaz.
- Veri bölümlerinin tutarlı anlık görüntüsü, recovery'de ilgili bölümler ayrılmışken alınır. Recovery arayüzünde veri silme/formatlama, `fastboot -w`, `erase`, relock veya bütün ROM'u tekrar yazma bu akışın parçası değildir.

Yalnız okuma örnekleri; gerçek yolları doğrulamak için:

```sh
adb -s "$DEVICE_SERIAL" shell id
adb -s "$DEVICE_SERIAL" shell cat /proc/mounts
adb -s "$DEVICE_SERIAL" shell readlink -f /dev/block/platform/bootdevice/by-name/nvram
adb -s "$DEVICE_SERIAL" shell readlink -f /dev/block/platform/bootdevice/by-name/nvdata
```

Bir bölüm yedeğinin örnek akışı: aşağıdaki `nvram` yerine diğer bölümleri otomatik döngüye sokmadan her bölümün adı, boyutu ve mount durumu ayrı kontrol edilir. `PRIVATE_BACKUP_DIR` temp altında izinleri 700 olan özel klasördür.

```sh
adb -s "$DEVICE_SERIAL" exec-out 'dd if=/dev/block/platform/bootdevice/by-name/nvram bs=1048576 2>/dev/null' \
  > "$PRIVATE_BACKUP_DIR/nvram.img"
```

Sıfır çıkış kodu tek başına yeterli değildir. Cihaz bölüm boyutu ile dosya boyutu aynı olmalı; cihaz tarafındaki `sha256sum` ile bilgisayardaki `shasum -a 256` eşleşmeli. Hash çıktıları özel kalır.

## 2. Etiket hatasını içerik değişiminden ayırma

Bu vakada dosyaların önceki içerik hashleri ve etiketleri kaydedildi. Stok platform+vendor file_contexts üzerinden `nvdata` altındaki üç dosya `u:object_r:nvdata_file:s0`, `protect_s` altındaki dosya `u:object_r:protect_s_data_file:s0` olarak düzeltildi. İçerik hashleri tekrar karşılaştırıldı.

Recovery'nin kendi `restorecon` kuralları stok ROM'dan farklı olabilir. Bu vakada kuru çalıştırma tüm NV ağacına yanlış genel etiket önerdiği için uygulanmadı. Bütün ağaca tahmini etiket vermek yerine doğrulanmış dört dosya sınırında kalındı. Sonraki `--show_bad_nv` kaydı ayrıca incelendi; etiket düzeltmesinin başarısı NV içerik doğrulamasının da geçtiği anlamına gelmedi.

## 3. Özel payload yazımı: ayrılmış bölüm ve tekrar okuma

İnceleme paketinin manifesti ile her payload'ın hash/boyutu özel alanda kontrol edilir. `nvram.img` ve `nvdata.img` için beklenen boyut **67108864 bayt**tır. Bu, bağlı telefondaki gerçek bölüm boyutu kontrolünün yerine geçmez.

Recovery'deki `/proc/mounts` okunur; NV bölümünün gerçek mount noktası bulunur. Bu vakada `/mnt/vendor/nvdata` kullanıldı. Yalnız `/nvdata` için unmount komutu çalıştırıp başarı varsayılmaz. Recovery farklı bir alias veya bind mount kullanıyorsa onlar da ayrılmalı; ilgili gerçek block device için hiçbir mount kaydı kalmamalıdır.

```sh
# Yalnız /proc/mounts bu noktayı doğruladıysa, kullanıcı başlatır:
adb -s "$DEVICE_SERIAL" shell umount /mnt/vendor/nvdata
adb -s "$DEVICE_SERIAL" shell cat /proc/mounts
```

NV bölümünün hâlâ bağlı olduğu, boyut/hash uyuşmadığı veya yedek doğrulanamadığı durumda durulur. Payload'lar recovery'nin RAM alanına aktarılır ve aktarım hashleri tekrar doğrulanır. Aşağıdaki komutlar yalnız bu kontroller tamamlandıktan sonra kullanıcı tarafından uygulanır:

```sh
adb -s "$DEVICE_SERIAL" push "$PRIVATE_PAYLOAD_DIR/nvram.img" /tmp/repair-nvram.img
adb -s "$DEVICE_SERIAL" push "$PRIVATE_PAYLOAD_DIR/nvdata.img" /tmp/repair-nvdata.img

# Her dd ayrı işlemdir; hata veya kısa yazmada sonraki komuta geçilmez.
adb -s "$DEVICE_SERIAL" shell 'dd if=/tmp/repair-nvram.img of=/dev/block/platform/bootdevice/by-name/nvram bs=1048576 && sync'
adb -s "$DEVICE_SERIAL" shell 'dd if=/tmp/repair-nvdata.img of=/dev/block/platform/bootdevice/by-name/nvdata bs=1048576 && sync'
```

Yazılan bölümlerin tamamı **tekrar okunur**; SHA-256 değerleri payload manifestiyle aynı olmalıdır. Yalnız `dd` çıktısına güvenilmez. Vendor adımına ancak bu kontrol geçince ilerlenir.

## 4. Vendor dosyaları ve verified boot

Stok vendor'a eklenecek yalnız iki dosya vardır. Vendor'ın gerçek block device ve mount noktası doğrulanır, `rw` bağlandığı ve yazılabildiği kontrol edilir. Aynı isimli dosyalar önceden varsa özel yedekleri alınır. Vendor mount başarısı ayrıca okunarak doğrulanmadan kopyalama yapılmaz.

```sh
adb -s "$DEVICE_SERIAL" push "$PRIVATE_PAYLOAD_DIR/vendor/lib/modules/md_patcher.ko" /vendor/lib/modules/md_patcher.ko
adb -s "$DEVICE_SERIAL" push "$PRIVATE_PAYLOAD_DIR/vendor/etc/init/md_patcher.rc" /vendor/etc/init/md_patcher.rc
adb -s "$DEVICE_SERIAL" shell 'chown 0:0 /vendor/lib/modules/md_patcher.ko /vendor/etc/init/md_patcher.rc && chmod 0644 /vendor/lib/modules/md_patcher.ko /vendor/etc/init/md_patcher.rc'
adb -s "$DEVICE_SERIAL" shell chcon u:object_r:vendor_file:s0 /vendor/lib/modules/md_patcher.ko
adb -s "$DEVICE_SERIAL" shell chcon u:object_r:vendor_configs_file:s0 /vendor/etc/init/md_patcher.rc
```

Dosyaların hashleri, boyutları, sahipliği, izinleri ve etiketleri tekrar okunur. Sonra sync ve vendor unmount yapılır. Kernel modülü **recovery çekirdeğine yüklenmez**; amaç stok Android'in kendi post-fs-data aşamasında yüklemesidir.

Değiştirilmiş vendor'ın stok hashtree ile doğrulanması beklenmez. Kullanıcının ayrı olarak başlattığı fastboot adımında **aynı ROM'un stok vbmeta dosyası** verification/verity kapatma seçenekleriyle yazılır; ürün/seri/bootloader durumu önceden doğrulanır:

```sh
fastboot -s "$DEVICE_SERIAL" --disable-verity --disable-verification flash vbmeta "$STOCK_VBMETA_IMAGE"
```

Yazılan vbmeta okunarak kapatma bayrakları ve beklenen içerik doğrulanır. “OKAY” tek başına yeterli değildir. Bootloader açık bırakılır; relock yapılmaz. Farklı ROM'un vbmeta dosyası rastgele kullanılmaz.

## 5. Açılışta ne doğrulanır?

Android açılışı, recovery'ye geri dönmemesi, `md_patcher` modülünün gerçekten yüklenmesi, init/kernel hataları, baseband/modem hazır durumu ve iki SIM yuvasının kimliği özel olarak kontrol edilir. Ardından SIM algısı, şebeke kaydı ve gerçek arama/veri testi yapılır. MAC/IMEI/chip değerleri hiçbir public loga yazılmaz. Zorlamalı modül yükleme kernel ABI güvencesi değildir.

Hoparlör, mikrofon, Wi-Fi, Bluetooth ve sensörler ayrı fiziksel testlerdir. Bu vakada hoparlör teşhisi devam ettiğinden yalnız Android'in açılması “telefon tamamen onarıldı” sonucu olarak sunulmaz.

## 6. Geri dönüş

Bu şablon yolu NVRAM, NVDATA ve iki vendor dosyasını değiştirir. Asgari geri dönüş, ayrılmış bölümlere doğrulanmış başlangıç NVRAM+NVDATA yedeklerini geri yazıp tekrar okuyarak doğrulamak ve eklenen vendor dosyalarını kaldırmak/önceki sürümlerini geri koymaktır. Magisk üzerinden ayrıca kurulum yapıldıysa onun modülü de ayrıca kaldırılır. Bu yardımcı Magisk kurulumu yapmaz.

Vendor değiştikten sonra yalnız iki dosyayı silmek ext4 metadata/verity ağacını stok hale getirmeyebilir. Stok vbmeta'ya dönmeden önce **aynı ROM'un stok vendor görüntüsü** geri yüklenip doğrulanmalı; recovery değişikliği de ayrıca geri alınmalıdır. Bootloader kilitlenmez.

Başlangıç yedeği etiket düzeltmesinden önce alınmışsa eski etiketleri de geri getirir. Başlangıç NVRAM tamamen sıfırsa bu geri dönüş çalışır şebekeyi garanti etmez; yalnız başlangıç verilerini korur. Bütün NV bölümlerini, userdata'yı veya başka ROM'u tahminen silmek geri dönüş yöntemi değildir.
