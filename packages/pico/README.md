Raspberry 5 - Pico ile microros üzerinden haberleşerek:



* Motor hız kontrolü
* Enkoder bilgileri
* Uçurum sensörleri
* Çarpma sensörleri
* Batarya durumu



bilgilerini düzenlemektedir.



Pico üzerindeki yazılımı güncellemek için aşağıdaki işlemler yapılmalıdır.



* orbirob\_pico.uf2 ve flash\_pico.sh dosyalarını indiriniz ve aşağıdaki komutları giriniz:



&#x09;chmod +x ./flash\_pico.sh



&#x09;./flash\_pico.sh          





İşlem sonrasında aşağıdaki komutları giriniz:



&#x09;sudo systemctl daemon-reload



&#x09;sudo systemctl restart micro\_ros\_agent



&#x09;veya



&#x09;sudo systemctl restart microros



&#x09;Not: Hangisi olacağını ls /etc/systemd/system/micro\*    yazarak bulabilirsiniz





