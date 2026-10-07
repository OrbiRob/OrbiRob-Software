OrbiRob executable ROS2 dosyalarını yüklemek için:



chmod +x ./update\_orbirob\_executables.sh



./update\_orbirob\_executables.sh


***** 260917 - 17-Eylül-2026 **********
- Temel enkoder ve tekerlek parametlerinin mimarisi değiştirildi
- Her robot için derleme gerektirmeden robot parametreleri oluşturuldu ($HOME/orbirob_calibration klasörü içinde)
- Dolayısı ile, robot yazılımları güncellense bile robota özgü parametreler saklı kalacak
- Pico temel motor hareketleri yapmakla birlikte, Pico üstünde bu parametreler saklanmıyor
- Yeni revizyonda süreç aşağıdaki şekilde gerçekleşmektedir:
  * Boot sonrası micro_ros_agent servisi otomatik olarak başlatılır
  * Sonrasında $HOME/orbirob_calibration/calibration.yaml dosyası içindeki bilgiler
    /pico/drive_config topic'i üzerinden pico'ya gönderilir
  * /pico/drive_config_status bu bilgilerin gönderilip gönderilmediği status'unu içerir
  * Robota kalibrasyon için aşağıdaki komut koşulur:
    ros2 run orbirob_calibration orbirob_calibrate
    Kalibrasyonun 2 bölümden oluşur:
    1) Lineer kalibrasyon (metre/enkoder_tick) - sağ ve sol için ayrı ayrı
    2) Angular kalibrasyon (tekerlekler arası mesafe)


  Kurulum için:
    1) Dosyaları indiriniz
    2) chmod +x ./update_orbirob_executables.sh
    3) ./update_orbirob_executables.sh
    4) chmod +x ./install_calibration_service.sh
    5) ./install_calibration_service.sh
    6) Default kalibrasyon değerleri $HOME/orbirob_calibration klasöründe oluşturulacaktır.
    7) Kalibrasyon ihtiyacı var ise, yukarıdaki kalibrasyon komutunu girerek kalibrasyon yapabilirsiniz.
    
***** 260916 - 16-Eylül-2026 **********


