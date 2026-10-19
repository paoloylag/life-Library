"""Versioned text transcribed from the library's two-page guidelines PDF."""
import hashlib
import json

GENERAL = [
    "All users must reserve a slot through the online booking system by scanning the QR Code prior to use. For Nap Pod reservations, only one (1) user may register per booking. For Collaboration Room reservations, the booking representative shall indicate the names of all members who will utilize the room during the reserved schedule.",
    "Users must confirm their reservation with the Librarian before use and surrender any valid ID in exchange for a nap pod / room pass. The ID will be returned once the pass is surrendered after use.",
    "Only user/s listed in the online booking form shall be allowed to enter and use the facility.",
    "Food and drinks are strictly prohibited inside the Nap Pods and Collaboration Rooms.",
    "Users are prohibited from rearranging furniture or transferring equipment without permission.",
    "Users are responsible for maintaining cleanliness and orderliness of the area, including proper waste disposal and returning furniture to its original arrangement after use.",
    "Any damage done to facilities, furniture, or equipment during the reserved session shall be the responsibility of the users.",
    "Failure to comply with these guidelines will result in suspension or revocation of Nap Pod and Collaboration Room privileges and will be subject to disciplinary action in accordance with the Student Manual.",
]
GUIDELINES = {
    "nap_pod": {
        "title": "Nap Pod Booking & Guidelines", "page": 1,
        "sections": [{"title": "General Guidelines", "items": GENERAL}, {"title": "Nap Pod Usage Guidelines", "items": [
            "The Nap Pod area is open to all bona fide LIFE College International students, faculty, and staff.",
            "Each booking is limited to a maximum of one (1) session of forty-five (45) minutes.",
            "Complete silence shall be observed in the Nap Pod area. The use of speakers or any device that may disturb other users is strictly prohibited. Users may use earphones/headphones at minimal volume.",
            "Users must set an alarm or timer for forty-five (45) minutes.",
            "The Nap Pod is intended solely for short rest periods. Users who are feeling unwell or sick are advised to proceed to the Clinic instead of using the Nap Pod.",
        ]}],
    },
    "collaboration_room": {
        "title": "Collaboration Room Booking & Guidelines", "page": 2,
        "sections": [{"title": "General Guidelines", "items": GENERAL}, {"title": "Collaboration Room Usage Guidelines", "items": [
            "The Collaboration Rooms are available exclusively to bona fide LIFE College International students, subject to availability and prior reservation.",
            "Each Collaboration Room may accommodate a maximum of eight (8) users at a time, preferably divided into two (2) groups with four (4) members each.",
            "Each reservation is limited to two (2) sessions at two (2) hours each.",
            "Laptops, tablets, and other academic-related devices may be used inside the Collaboration Rooms. Discussions shall be conducted at a moderate volume to avoid disturbing other library users. Playing loud music, gaming, or non-academic activities that may cause disruption are prohibited.",
            "The Collaboration Rooms are intended strictly for academic discussions, group study, meetings, and collaborative learning activities. Sleeping and other non-academic activities are strictly prohibited.",
        ]}],
    },
}
GUIDELINES_VERSION = hashlib.sha256(json.dumps(GUIDELINES, sort_keys=True).encode()).hexdigest()


def guideline(kind):
    document = GUIDELINES.get(kind)
    return None if document is None else {
        **document, "version": GUIDELINES_VERSION, "contact": "library@life.edu.ph",
        "source": "NAP POD & COLLAB ROOM BOOKING & GUIDELINES.pdf",
    }
