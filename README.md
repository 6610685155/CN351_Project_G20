# CN351_Project_G20
# Budgy - Manage Your Finances

## Members

1.Athichart Penwong            6610685015\
2.Krittin Dansai                   6610685031\
3.Natthasit Thitithammakun   6610685155\
4.Supawich Boonpraseart     6610685346\


---



## Install & Run (Dev)
1. Clone github repo
```
git clone https://github.com/6610685031/cn331-project-budgy
cd cn331-project-budgy/budgy
```

2. Create virtual environment and install package
```
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```
>If you don't have pip installed, please refer to the Python official website: https://packaging.python.org/en/latest/tutorials/installing-packages/

3. Crate Database
```
cd budgy
python manage.py makemigrations
python manage.py migrate
```

4. Create Admin
```
python manage.py createsuperuser
```

5. Run server
```
python manage.py runserver
```

Extra: Clear local Database 
```
python manage.py flush
```

