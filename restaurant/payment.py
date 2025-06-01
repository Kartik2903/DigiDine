import razorpay
from django.conf import settings
from django.http import JsonResponse
from .models import Order

client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

def create_razorpay_order(order):
    """Create a Razorpay order for the given order"""
    try:
        # Convert amount to paise (Razorpay expects amount in smallest currency unit)
        amount = int(float(order.total) * 100)
        
        # Create Razorpay order
        razorpay_order = client.order.create({
            'amount': amount,
            'currency': 'INR',
            'receipt': f'order_{order.id}',
            'notes': {
                'order_id': str(order.id)
            }
        })
        
        # Update order with Razorpay order ID
        order.razorpay_order_id = razorpay_order['id']
        order.save()
        
        return razorpay_order
    except Exception as e:
        print(f"Error creating Razorpay order: {str(e)}")
        return None

def verify_payment(payment_id, order_id, signature):
    """Verify the payment signature"""
    try:
        params_dict = {
            'razorpay_payment_id': payment_id,
            'razorpay_order_id': order_id,
            'razorpay_signature': signature
        }
        
        client.utility.verify_payment_signature(params_dict)
        return True
    except Exception as e:
        print(f"Payment verification failed: {str(e)}")
        return False 