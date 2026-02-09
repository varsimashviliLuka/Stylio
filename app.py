from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def hello_world():
    salons = [
    {
        "id": 1,
        "name": "Glamour Glow Salon",
        "description": "A chic urban salon offering haircuts, coloring, and spa treatments with a modern touch.",
        "location": "123 Main St, New York, NY",
        "tags": ["hair", "spa", "coloring", "manicure"],
        "review_count": 124,
        "average_review": 4.7,
        "photos": [
            "https://images.squarespace-cdn.com/content/v1/629c1d4d36ad5457be71d4f3/1687240940607-K6S0WGASFZ3GP1NP622E/BR_Play+Salon_internal01.jpg",
            "https://p.turbosquid.com/ts-thumb/YX/NJ1hJD/F9Hx877w/hairsaloon_07/jpg/1608800333/1920x1080/fit_q87/3c251e9e5b26952159268a3681b99c129c48338e/hairsaloon_07.jpg",
            "https://wallpapers.com/images/hd/beauty-salon-haircut-16616h5k4y5xrcxx.jpg"
        ]
    },
    {
        "id": 2,
        "name": "Urban Edge Studio",
        "description": "Trendy salon specializing in edgy hairstyles and contemporary beauty services for all ages.",
        "location": "456 Elm St, Los Angeles, CA",
        "tags": ["hair", "styling", "trendy", "cut"],
        "review_count": 98,
        "average_review": 4.5,
        "photos": [
            "https://backoffice.vilavitaparc.com/sites/default/files/styles/heroimg/public/2022-02/_TAL3113-VilaVitaAnita.jpeg?itok=nQtR_11-",
            "https://uploads.montage.com/uploads/sites/4/2021/09/29093927/MHH2-SPA-02-SALON-1801-edit-1920x1080.jpeg"
        ]
    },
    {
        "id": 3,
        "name": "Serenity Spa & Salon",
        "description": "Relaxing environment offering massages, facials, and premium hair services for ultimate rejuvenation.",
        "location": "789 Oak St, Chicago, IL",
        "tags": ["spa", "massage", "facial", "haircare"],
        "review_count": 210,
        "average_review": 4.8,
        "photos": []  # no photos, will use default
    },
    {
        "id": 4,
        "name": "Classic Cuts",
        "description": "Family-friendly salon delivering classic haircuts, styling, and beauty treatments with a personal touch.",
        "location": "321 Pine St, Austin, TX",
        "tags": ["hair", "family", "cuts", "styling"],
        "review_count": 87,
        "average_review": 4.3,
        "photos": [
            "https://images.squarespace-cdn.com/content/v1/629c1d4d36ad5457be71d4f3/1687240940607-K6S0WGASFZ3GP1NP622E/BR_Play+Salon_internal01.jpg"
        ]
    }
]

    return render_template('./index/index.html', salons=salons)
