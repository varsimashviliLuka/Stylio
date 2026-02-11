from flask import Flask, render_template, request, redirect, url_for, jsonify
app = Flask(__name__)

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
        ],
        "services": [
            {"name": "Signature Haircut", "duration": 60, "price": 85},
            {"name": "Hair Coloring", "duration": 120, "price": 150},
            {"name": "Spa Manicure", "duration": 45, "price": 45},
            {"name": "Deluxe Facial", "duration": 75, "price": 120}
        ],
        "staff": [
            {
                "name": "Anna Roberts",
                "profession": "Hair Stylist",
                "skills": ["Signature Haircut"],
                "image": "https://randomuser.me/api/portraits/women/44.jpg"
            },
            {
                "name": "Michael Lee",
                "profession": "Color Specialist",
                "skills": ["Hair Coloring"],
                "image": "https://randomuser.me/api/portraits/men/32.jpg"
            },
            {
                "name": "Sophia Kim",
                "profession": "Manicurist",
                "skills": ["Spa Manicure"],
                "image": "https://randomuser.me/api/portraits/women/68.jpg"
            }
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
        ],
        "services": [
            {"name": "Modern Haircut", "duration": 60, "price": 75},
            {"name": "Beard Trim", "duration": 30, "price": 35},
            {"name": "Hair Styling", "duration": 45, "price": 55}
        ],
        "staff": [
            {
                "name": "Chris Walker",
                "profession": "Barber",
                "skills": ["Modern Haircut", "Beard Trim"],
                "image": "https://randomuser.me/api/portraits/men/46.jpg"
            },
            {
                "name": "Emily Stone",
                "profession": "Hair Stylist",
                "skills": ["Modern Haircut", "Hair Styling"],
                "image": "https://randomuser.me/api/portraits/women/65.jpg"
            }
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
        "photos": [],
        "services": [
            {"name": "Full Body Massage", "duration": 90, "price": 150},
            {"name": "Hot Stone Therapy", "duration": 75, "price": 130},
            {"name": "Luxury Facial", "duration": 80, "price": 140}
        ],
        "staff": [
            {
                "name": "Olivia Brown",
                "profession": "Massage Therapist",
                "skills": ["Full Body Massage", "Hot Stone Therapy"],
                "image": "https://randomuser.me/api/portraits/women/50.jpg"
            },
            {
                "name": "Daniel Park",
                "profession": "Spa Specialist",
                "skills": ["Luxury Facial", "Hot Stone Therapy"],
                "image": "https://randomuser.me/api/portraits/men/53.jpg"
            }
        ]
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
        ],
        "services": [
            {"name": "Classic Haircut", "duration": 45, "price": 40},
            {"name": "Kids Haircut", "duration": 30, "price": 25},
            {"name": "Hair Wash & Style", "duration": 50, "price": 55}
        ],
        "staff": [
            {
                "name": "Laura Green",
                "profession": "Senior Stylist",
                "skills": ["Classic Haircut", "Hair Wash & Style", "Kids Haircut"],
                "image": "https://randomuser.me/api/portraits/women/32.jpg"
            },
            {
                "name": "James Carter",
                "profession": "Barber",
                "skills": ["Classic Haircut", "Kids Haircut"],
                "image": "https://randomuser.me/api/portraits/men/41.jpg"
            },
            {
                "name": "Jamessss Caffffrter",
                "profession": "Barber",
                "skills": ["Classic Haircut", "Kids Haircut"],
                "image": "https://randomuser.me/api/portraits/men/45.jpg"
            },

        ]
    }
]


@app.route('/')
def home_page():
    

    return render_template('./index/index.html', salons=salons)

@app.route('/book/<int:id>', methods=['GET', 'POST'])
def book_a_visit(id):
    salon = next((s for s in salons if s["id"] == id), None)

    if request.method == 'POST':
        data = request.form.to_dict()
        print("BOOKING RECEIVED:", data, flush=True)

        # later you’ll save this to DB, send email, etc.
        return jsonify({"ok": True, "message": "Booking received"}), 200

    return render_template('./book_a_visit/book_a_visit.html', salon=salon)