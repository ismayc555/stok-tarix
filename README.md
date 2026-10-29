# Stok tarix nəzarəti

Azərbaycan dilində məhsul partiyalarının son istifadə tarixini izləyən yerli tətbiq.

## Başlatmaq

Python 3 tələb olunur. Əlavə paket lazım deyil.

```sh
python3 /home/ismayc555/claude-work/stok-tarix/server.py
```

Brauzerdə `http://127.0.0.1:8765` ünvanını açın. Server işlədiyi müddətdə səhifə bazaya qoşulur. Serveri dayandırmaq üçün Ctrl+C istifadə edin.

## İstifadə

- Məhsul adı və stok miqdarı məcburidir. Son istifadə tarixi boş qala bilər; belə qeydlər sarı rəngdə “Tarix bilinmir” kimi göstərilir.
- Barkod, partiya nömrəsi və rəf istəyə bağlıdır.
- Eyni məhsulun müxtəlif tarixli partiyalarını ayrı sətirlərdə əlavə edin.
- 0–15 gün qalan və tarixi keçmiş partiyalar qırmızı göstərilir. Bu gün bitənlər ayrıca yazı ilə işarələnir.
- Tarix Bakı vaxtına əsaslanır və açıq səhifədə hər dəqiqə yenidən hesablanır.
- Axtarış, tarix süzgəci, düzəliş və təsdiqli silmə mövcuddur.
- Məlumatlar `stock.sqlite3` faylında saxlanılır; brauzeri bağlamaq məlumatları silmir.

## Əhatə və məhdudiyyətlər

CSV toplu idxalı və ixracı, sütun uyğunlaşdırması, önbaxış, rəf süzgəci, sıralama, səhifələmə və işıqlı/qaranlıq rejim mövcuddur. Excel faylını CSV UTF-8 formatına çevirin; bir idxalda maksimum 10 000 qeyd və 5 MB dəstəklənir. Ad və miqdar sütunlarını seçmək məcburidir. Tarix YYYY-MM-DD və ya DD.MM.YYYY ola bilər.

Tam eyni qeydlər təkrar idxalda ötürülür. Dəyişmiş miqdar və ya digər sahələr yeni qeyd yaradır; idxal stok sinxronizasiyası deyil və mövcud qeydləri əvəzləmir. Səhv sətir aşkar ediləndə idxal bütövlükdə rədd olunur. CSV ixracı bütün süzgəcdən keçmiş qeydləri, səhifələmədən asılı olmayaraq, götürür.

Bu, tək kompüter üçün versiyadır. Birbaşa XLSX idxalı, mövcud mağaza stok sistemi ilə inteqrasiya, istifadəçi hesabları, avtomatik satış çıxılması və SMS/e-poçt xəbərdarlığı yoxdur. Rəng xəbərdarlığı səhifə açıldıqda görünür. Son istifadə tarixi adi barkoddan avtomatik müəyyən edilmir; hər partiya üçün daxil edilməlidir.

Server yalnız bu kompüterdən açılan localhost ünvanında dinləyir. Bunu mağaza şəbəkəsinə açmaq üçün əvvəl kimlik doğrulaması, səlahiyyətlər, HTTPS və ehtiyat nüsxə siyasəti əlavə edilməlidir. Real stok məlumatlarını yalnız rəhbərliyin icazəsi ilə daxil edin. Ehtiyat nüsxə üçün server dayandırılmış halda `stock.sqlite3` faylının surətini təhlükəsiz yerə götürün.

Tətbiq yerli serverdən istifadə üçün hazırlanıb; bu versiya onlayn yayımlanmayıb. İstifadə təlimatı saytın “İstifadə qaydası” bölməsində də var.
