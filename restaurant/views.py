from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from .models import MenuItem, Order, OrderItem
from django.views.decorators.http import require_POST
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.utils import timezone
from .payment import create_razorpay_order, verify_payment
from django.conf import settings
from django.contrib.auth.models import User
import json

def get_cart_count(request):
    cart = request.session.get('cart', {})
    return sum(item['quantity'] for item in cart.values())

def home(request):
    menu_items = MenuItem.objects.all()
    search_query = request.GET.get('search', '')
    category = request.GET.get('category', '')
    
    if search_query:
        menu_items = menu_items.filter(name__icontains=search_query)
    
    if category:
        menu_items = menu_items.filter(category=category)
    
    # Get unique categories for filter
    categories = MenuItem.objects.values_list('category', flat=True).distinct()
    
    context = {
        'menu_items': menu_items,
        'search_query': search_query,
        'selected_category': category,
        'categories': categories,
        'cart_count': get_cart_count(request)
    }
    return render(request, 'restaurant/home.html', context)

@require_POST
def add_to_cart(request, item_id):
    try:
        data = json.loads(request.body)
        quantity = int(data.get('quantity', 1))
        
        if quantity < 1:
            return JsonResponse({
                'success': False,
                'error': 'Quantity must be at least 1'
            }, status=400)
        
        menu_item = get_object_or_404(MenuItem, id=item_id)
        cart = request.session.get('cart', {})
        
        if str(item_id) in cart:
            cart[str(item_id)]['quantity'] += quantity
        else:
            cart[str(item_id)] = {
                'name': menu_item.name,
                'price': str(menu_item.price),
                'quantity': quantity
            }
        
        request.session['cart'] = cart
        request.session.modified = True
        
        return JsonResponse({
            'success': True,
            'cart_count': get_cart_count(request)
        })
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid request data'
        }, status=400)
    except ValueError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid quantity value'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

def cart(request):
    cart = request.session.get('cart', {})
    cart_items = []
    total = 0
    
    for item_id, item_data in cart.items():
        menu_item = get_object_or_404(MenuItem, id=item_id)
        cart_items.append({
            'id': item_id,
            'name': item_data['name'],
            'price': float(item_data['price']),
            'quantity': item_data['quantity'],
            'subtotal': float(item_data['price']) * item_data['quantity']
        })
        total += float(item_data['price']) * item_data['quantity']
    
    context = {
        'cart_items': cart_items,
        'total': total,
        'cart_count': get_cart_count(request)
    }
    return render(request, 'restaurant/cart.html', context)

def receipt(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'restaurant/receipt.html', {'order': order})

@login_required
def dashboard(request):
    if not request.user.is_staff:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('home')

    # Only show active orders (not completed)
    orders = Order.objects.exclude(status='completed').order_by('-created_at')

    return render(request, 'restaurant/dashboard.html', {
        'orders': orders
    })

def staff_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None and user.is_staff:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid credentials or insufficient permissions.')

    return render(request, 'restaurant/staff_login.html')

@login_required
def staff_logout(request):
    logout(request)
    return redirect('home')

@login_required
def cancel_order(request, order_id):
    order = Order.objects.get(id=order_id)
    order.status = 'cancelled'
    order.save()
    return redirect('dashboard')

@login_required
def pickup_order(request, order_id):
    order = Order.objects.get(id=order_id)
    order.status = 'picked_up'
    order.save()
    return redirect('dashboard')

@require_POST
def update_cart_item(request, item_id):
    order_item = OrderItem.objects.get(id=item_id)
    action = request.POST.get('action')
    
    if action == 'increase':
        order_item.quantity += 1
    elif action == 'decrease':
        if order_item.quantity > 1:
            order_item.quantity -= 1
        else:
            order_item.delete()
            return redirect('cart')
    
    order_item.save()
    
    # Update order total
    order = order_item.order
    order.total = sum(item.price * item.quantity for item in order.items.all())
    order.save()
    
    return redirect('cart')

@require_POST
def remove_cart_item(request, item_id):
    order_item = OrderItem.objects.get(id=item_id)
    order = order_item.order
    order_item.delete()
    
    # Update order total
    order.total = sum(item.price * item.quantity for item in order.items.all())
    order.save()
    
    return redirect('cart')

@require_POST
def place_order(request):
    session_key = request.session.session_key
    order = Order.objects.filter(session_key=session_key, status='pending').first()
    
    if order and order.items.exists():
        # Create Razorpay order
        razorpay_order = create_razorpay_order(order)
        if razorpay_order:
            return JsonResponse({
                'success': True,
                'order_id': razorpay_order['id'],
                'amount': razorpay_order['amount'],
                'currency': razorpay_order['currency'],
                'key': settings.RAZORPAY_KEY_ID
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Failed to create payment order'
            })
    
    return JsonResponse({
        'success': False,
        'error': 'No items in cart'
    })

@require_POST
def verify_payment_callback(request):
    """Handle Razorpay payment callback"""
    payment_id = request.POST.get('razorpay_payment_id')
    order_id = request.POST.get('razorpay_order_id')
    signature = request.POST.get('razorpay_signature')
    
    if verify_payment(payment_id, order_id, signature):
        # Update order status
        order = Order.objects.get(razorpay_order_id=order_id)
        order.payment_status = 'completed'
        order.razorpay_payment_id = payment_id
        order.status = 'preparing'  # Move to preparing state
        order.save()
        
        return JsonResponse({
            'success': True,
            'redirect_url': f'/receipt/{order.id}/'
        })
    
    return JsonResponse({
        'success': False,
        'error': 'Payment verification failed'
    })

@login_required
@require_POST
def update_order_status(request, order_id):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    try:
        data = json.loads(request.body)
        new_status = data.get('status')
        # Accept both 'completed' and 'ready' as valid statuses
        if new_status not in ['pending', 'preparing', 'ready', 'completed']:
            return JsonResponse({'error': f'Invalid status: {new_status}'}, status=400)
        order = get_object_or_404(Order, id=order_id)
        order.status = new_status
        order.save()
        return JsonResponse({
            'success': True,
            'order': {
                'id': order.id,
                'status': order.status,
                'status_display': order.get_status_display(),
                'items_count': order.orderitem_set.count(),
                'total': order.total,
                'created_at': order.created_at.isoformat()
            }
        })
    except Exception as e:
        import traceback; traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=400)

@login_required
def order_details(request, order_id):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    order = get_object_or_404(Order, id=order_id)
    items = order.orderitem_set.all()
    
    return JsonResponse({
        'items': [{
            'name': item.menu_item.name,
            'price': item.menu_item.price,
            'quantity': item.quantity
        } for item in items],
        'total': order.total
    })

@login_required
def discard_order(request, order_id):
    order = Order.objects.get(id=order_id)
    order.status = 'discarded'
    order.save()
    return redirect('dashboard')

@require_POST
def remove_from_cart(request, item_id):
    cart = request.session.get('cart', {})
    if str(item_id) in cart:
        del cart[str(item_id)]
        request.session['cart'] = cart
        request.session.modified = True
    return redirect('cart')

@require_POST
def checkout(request):
    cart = request.session.get('cart', {})
    if not cart:
        messages.error(request, 'Your cart is empty')
        return redirect('cart')
    
    payment_method = request.POST.get('payment_method', 'cash')
    
    # Create order
    order = Order.objects.create(
        total=sum(float(item['price']) * item['quantity'] for item in cart.values()),
        status='pending',
        payment_status='pending',
        payment_method=payment_method
    )
    
    # Create order items
    for item_id, item_data in cart.items():
        menu_item = get_object_or_404(MenuItem, id=item_id)
        OrderItem.objects.create(
            order=order,
            menu_item=menu_item,
            quantity=item_data['quantity'],
            price=float(item_data['price'])
        )
    
    # Clear cart
    request.session['cart'] = {}
    request.session.modified = True
    
    messages.success(request, 'Order placed successfully!')
    return redirect('receipt', order_id=order.id)
