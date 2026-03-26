import os
import sys

# ১. পাথ বুটস্ট্র্যাপ (Path Bootstrap)
# ভার্সেল ল্যাম্বডা ফাংশনের ভেতরে __file__ হলো /var/task/api/index.py
# প্রজেক্ট রুট (যেখানে app/, templates/ এবং static/ আছে) এক ধাপ উপরে অবস্থিত।
_HERE = os.path.dirname(os.path.abspath(__file__))   # .../api [cite: 8]
_PROJECT_ROOT = os.path.dirname(_HERE)               # .../ (repo root) [cite: 8]

# নিশ্চিত করা হচ্ছে যেন প্রোজেক্ট রুট sys.path এ থাকে যাতে `from app import ...` কাজ করে।
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT) [cite: 8]

# ২. ফ্লস্ক অ্যাপ তৈরি (Create Flask App)
try:
    from app import create_app [cite: 9]
    
    # প্রোডাকশন মোডে অ্যাপ ইনিশিয়ালাইজ করা
    # এটি config.py থেকে ProductionConfig লোড করবে 
    app = create_app(os.environ.get("FLASK_ENV", "production")) [cite: 9]

except Exception as e:
    # যদি ইম্পোর্ট এরর হয়, তবে সেটি ডিবাগিংয়ের জন্য প্রিন্ট করা
    print(f"Error initializing Flask app: {e}")
    raise e

# ৩. ভার্সেল হ্যান্ডলার (Vercel Handler)
# ভার্সেল সরাসরি এই 'app' অবজেক্টটি WSGI হিসেবে কল করবে [cite: 9]
# লোকাল টেস্টিংয়ের জন্য নিচের অংশটি রাখা হয়েছে (python api/index.py)
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False,
    ) [cite: 9]