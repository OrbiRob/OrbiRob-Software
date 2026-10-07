# OrbiRob Public Packages & Demos
**other-code** klasöründe raspberry ile ilgili genel düzeltmeler, vs. kodları bulunmaktadır.
**packages** klasöründe OrbiRob ROS2 kodları ve pico üzerinde koşan microros kodları bulunmaktadır.
**demos** klasöründe yapılabilecek demo kodları bulunacaktır.

YAZILIMLARI GÜNCELLEMEK İÇİN AŞAĞIDAKİ ADIMLAR GERÇEKLEŞTİRİLMELİDİR:

1)	Fix_terminal						
	Raspberry - Ubuntu kodlarındaki bir bug sebebi ile terminal'in gelmesi 2dk üstünde sürmekte						
		other_code/fix_terminal					
		chmod +x  ./fix_terminal.sh					
		./fix_terminal.sh					
							
2)	Fix flicker - Login ekranında ekran açılana kadar titreşim oluşması						
		other_code/login_flicker					
		README.md içinde yazılı işlemler yapılmalı					
							
							
3)	Güncel OrbiRob-TFT ekranında koşan yazılımın yüklenmesi						
	packages/orbirob-tft-ui/v1.3.0						
	orbirob-tft-ui / v1.3.0 - içindeki dosyaları ~/tft klasörüne kopyalayalım						
	cp *.py  ~/tft						
	(İşlem sonrası reboot yapılması gerekmektedir)						
							
4)	orbirob GUI örnek yazılımının güncellenmesi						
	packages/orbirob-gui/1.1.0						
	chmod +x ./update_executables.sh						
	./update_executables						
							
5)	Pico yazılımının güncellenmesi						
	packages/pico/1.2.0						
	chmod +x ./flash_pico.sh						
	./flash_pico.sh						
							
							
6)	orbirob-base.service 						
	Bu servisin 2 işlevi vardır:						
	a) /etc/orbirob/calibration.yaml - dosyasını okuyarak - /pico/drive_config 'e publish eder						
	     (Bu işlem pico teyit gönderene kadar devam eder)						
	b) TFT ekrandan /emergency_stop topic'i gelirse, bunu /orbirob/emergency_stop_active'e publish eder						
	packages/orbirob-base						
	mkdir ~/orbirob_calibration						
	mv calibration.yaml ~/orbirob_calibration						
	sudo bash install.sh /home/orbirob/orbirob_calibration/calibration.yaml						
							
7)	Raspberry AI HAT+ (13 TOPS)						
	Daha kolay olarak AI HAT+ yazılımlarını yüklemek için hazırlanan script (ve ilgili driver'lar, dosyalar, vs.)						
	other-code/rpi_ai_hat+/						
	chmod +x ./install_orbirob_hailo_r1.sh						
	sudo ./install_orbirob_hailo_r1.sh						
							
8)	sudo nano /boot/firmware/config.txt						
	En sonunda [all] altında						
	[all]						
	usb_max_current_enable=1				eklensin		
							
	Bu işlem sonunda raspberry'i tekrar boot etmek gerekiyor						
	vcgencmd get_config usb_max_current_enable						komutunu koşunca
	   usb_max_current_enable=1						görmek gerekiyor
