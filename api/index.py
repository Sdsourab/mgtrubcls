import os
import sys

# প্রোজেক্ট রুটকে পাথ এ যুক্ত করা
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# এখানে [cite: 9] মুছে ফেলা হয়েছে
from app import create_app

# Vercel এর জন্য app অবজেক্টটি সরাসরি এক্সপোজ করা
app = create_app(os.environ.get("FLASK_ENV", "production"))

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False,
    )