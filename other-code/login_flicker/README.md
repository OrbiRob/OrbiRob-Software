

\*\*\* Problem: Login ekranında şifre girildikten sonra, ekranda login tamamlana kadar titreme oluyor.



\*\*\* Çözüm: Problemin kaynağı X11 ile ilişkili olup, aşağıdaki çözümü kullanabilirsiniz.



&#x09;sudo gedit /etc/gdm3/custom.conf



&#x09;Burada WaylandEnble=false olarak satırı, önüne '#' işareti koyarak devre dışı bırakıyoruz.



&#x09;WaylandEnable=false ==> #WaylandEnable=false



&#x09;olacak.





&#x09;Yaptığı işlem ise, login esnasında Wayland kullanılıyor - login sonrası ise X11 ile devam ediliyor.





