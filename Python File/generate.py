import qrcode
from PIL import Image  # Import the Image module

def generate_qr_code(data, filename):
    """
    Generates a QR code from the given data and saves it as an image.

    Args:
        data (str): The data to be encoded in the QR code.
        filename (str): The name of the file to save the QR code as (e.g., "booking_qr.png").
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img.save(filename)
    print(f"QR code generated and saved as {filename}")

# Example usage
name = "John Doe"
booking_details = "Booking ID: 12345, Date: 2024-07-15"
data_to_encode = f"Name: {name}\n{booking_details}"

generate_qr_code(data_to_encode, "booking_qr.png")


# To read the QR code (optional)
# import cv2
# img = cv2.imread("booking_qr.png")
# detector = cv2.QRCodeDetector()
# data, bbox, straight_qrcode = detector.detectAndDecode(img)
# if bbox is not None:
#     print(f"Decoded data from QR code: {data}")