"""
SEO: canonical URL, default Open Graph image, public site base for JSON-LD.
"""
import json

from django.conf import settings
from django.templatetags.static import static


def site_seo(request):
    path = request.path_info or "/"
    try:
        canonical_url = request.build_absolute_uri(path)
    except Exception:
        canonical_url = f"{getattr(settings, 'PUBLIC_SITE_URL', 'http://127.0.0.1:8000').rstrip('/')}{path}"
    public = getattr(settings, "PUBLIC_SITE_URL", "http://127.0.0.1:8000").rstrip("/")
    try:
        og_path = static("image.png")
        og_image = request.build_absolute_uri(og_path)
    except Exception:
        og_image = f"{public}{static('image.png')}"
    name = getattr(settings, "COMPANY_NAME", "MOGHAMO EXPRESS")
    phone = getattr(settings, "COMPANY_SUPPORT_PHONE", "+237675315422")
    org_ld = {
        "@context": "https://schema.org",
        "@type": "TravelAgency",
        "name": name,
        "url": public,
        "telephone": phone,
        "address": {
            "@type": "PostalAddress",
            "addressLocality": "Douala",
            "addressCountry": "CM",
        },
        "description": "Intercity bus booking and travel across Cameroon.",
    }
    return {
        "canonical_url": canonical_url,
        "og_image": og_image,
        "public_site_url": public,
        "seo_default_description": (
            "Book intercity bus tickets in Cameroon. MOGHAMO EXPRESS — online booking, "
            "routes, secure payment, and 24/7 support."
        ),
        "organization_json_ld": json.dumps(org_ld, ensure_ascii=True),
    }
