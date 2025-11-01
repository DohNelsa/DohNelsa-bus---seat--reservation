from django.shortcuts import render, redirect
from . forms import LoginForm, BookingForm
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .forms import BookingForm

from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Bus, Seat, Booking, Schedule, Route, Passenger, Payment, Support, BookingGroup
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Seat
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db.models import Sum
from django.core.paginator import Paginator
from django.utils import timezone
import json
from datetime import datetime, timedelta, time
import random
from django.db.models import Q
from django.core.mail import send_mail
from django.conf import settings

# SMS functionality disabled
# from .sms_service import send_booking_confirmation_sms, send_booking_cancellation_sms

# Create your views here.
def index(request):
    return render(request, 'NelsaApp/index.html')
def about_view(request):
    return render(request, 'NelsaApp/about.html')

#Registration
def register(request):
    from .forms import RegistrationForm
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            # Check if username already exists before saving
            username = form.cleaned_data.get('username')
            email = form.cleaned_data.get('email')
            phone_number = form.cleaned_data.get('phone_number')
            
            if User.objects.filter(username=username).exists():
                messages.error(request, "Username already exists. Please choose a different username.")
            elif User.objects.filter(email=email).exists():
                messages.error(request, "Email already exists. Please use a different email address.")
            else:
                try:
                    user = form.save()
                    login(request, user)
                    messages.success(request, "Registration successful! Welcome to MOGHAMO EXPRESS!")
                    return redirect('index')
                except Exception as e:
                    # Handle any other database errors
                    messages.error(request, f"Registration failed. Please try again. Error: {str(e)}")
        else:
            # Handle form validation errors with more specific messages
            if 'username' in form.errors:
                if 'already exists' in str(form.errors['username']):
                    messages.error(request, "Username already exists. Please choose a different username.")
                else:
                    messages.error(request, "Username is invalid. Please use only letters, numbers, and underscores.")
            elif 'email' in form.errors:
                if 'already exists' in str(form.errors['email']):
                    messages.error(request, "Email already exists. Please use a different email address.")
                else:
                    messages.error(request, "Please enter a valid email address.")
            elif 'phone_number' in form.errors:
                messages.error(request, "Please enter a valid phone number.")
            elif 'password2' in form.errors:
                if 'match' in str(form.errors['password2']):
                    messages.error(request, "Passwords don't match. Please try again.")
                else:
                    messages.error(request, "Password is too weak. Please choose a stronger password.")
            else:
                messages.error(request, "Registration failed. Please correct the errors.")
    else:
        form = RegistrationForm()
    return render(request, 'NelsaApp/register.html', {'form':form})
def Login_view(request):
    if request.method == 'POST':
        form = LoginForm(request=request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                
                # Redirect based on user type
                if user.is_staff:
                    return redirect('admin_dashboard')
                else:
                    # Check if there's a next parameter in the URL
                    next_url = request.GET.get('next')
                    if next_url:
                        return redirect(next_url)
                    else:
                        return redirect('index')
            else:
                messages.error(request, "Invalid username or password.")
    else:
        form = LoginForm()
    return render(request, 'NelsaApp/Login.html', {'form':form})

def logout_view(request):
    logout(request)
    return redirect('index')

def book_view(request):
    form = BookingForm
    if request.method == "POST":
        form = BookingForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('booking_success')  # Redirect to a success page
    else:
        form = BookingForm()
    return render(request, 'NelsaApp/Booking.html', {'form':form})

# New booking page view
def booking_page(request):
    """
    View for the booking page that displays available rides.
    """
    # Get filter parameters from request
    from_location = request.GET.get('from', '')
    to_location = request.GET.get('to', '')
    date = request.GET.get('date', '')
    
    # Base query for schedules with fresh data
    schedules = Schedule.objects.select_related('bus', 'route').filter(
        departure_time__gte=timezone.now(),
        is_available=True
    ).order_by('departure_time')
    
    # Apply filters if provided
    if from_location:
        schedules = schedules.filter(route__start_location__icontains=from_location)
    if to_location:
        schedules = schedules.filter(route__end_location__icontains=to_location)
    if date:
        try:
            date_obj = datetime.strptime(date, '%Y-%m-%d').date()
            schedules = schedules.filter(departure_time__date=date_obj)
        except ValueError:
            pass
    
    # Get all available routes for the filter dropdown
    all_routes = Route.objects.all().order_by('start_location')
    
    # If no schedules found, create sample schedules for demonstration
    if not schedules.exists():
        # Create sample routes if they don't exist
        routes_data = [
            {'start_location': 'Yaounde', 'end_location': 'Douala', 'distance': 250, 'duration': 4, 'price': 6000},
            {'start_location': 'Yaounde', 'end_location': 'Bamenda', 'distance': 350, 'duration': 6, 'price': 9000},
            {'start_location': 'Douala', 'end_location': 'Limbe', 'distance': 70, 'duration': 1.5, 'price': 4000},
            {'start_location': 'Douala', 'end_location': 'Buea', 'distance': 60, 'duration': 1, 'price': 3000},
            {'start_location': 'Bamenda', 'end_location': 'Douala', 'distance': 300, 'duration': 5, 'price': 7000},
        ]
        
        for route_data in routes_data:
            route, created = Route.objects.get_or_create(
                start_location=route_data['start_location'],
                end_location=route_data['end_location'],
                defaults={
                    'distance': route_data['distance'],
                    'duration': route_data['duration'],
                    'price': route_data['price']
                }
            )
            
            # Update existing routes with duration and price if they don't have them
            if not created and (not hasattr(route, 'duration') or not hasattr(route, 'price')):
                route.duration = route_data['duration']
                route.price = route_data['price']
                route.save()
        
        # Create sample buses if they don't exist
        bus_types = ['Luxury', 'Standard', 'Express']
        for i in range(1, 6):
            Bus.objects.get_or_create(
                bus_number=f'BUS-{i:03d}',
                defaults={
                    'bus_type': random.choice(bus_types),
                    'capacity': random.choice([30, 40, 50]),
                    'is_available': True
                }
            )
        
        # Create sample schedules for the next 7 days
        today = timezone.now().date()
        for i in range(7):
            current_date = today + timedelta(days=i)
            
            # Get all routes and buses
            routes = Route.objects.all()
            buses = Bus.objects.filter(is_available=True)
            
            # Create 2-3 schedules per day
            for _ in range(random.randint(2, 3)):
                route = random.choice(routes)
                bus = random.choice(buses)
                
                # Create departure time between 6 AM and 8 PM
                hour = random.randint(6, 20)
                minute = random.choice([0, 15, 30, 45])
                departure_time = datetime.combine(current_date, time(hour, minute))
                departure_time = timezone.make_aware(departure_time)
                
                # Calculate arrival time based on route duration
                arrival_time = departure_time + timedelta(hours=route.duration)
                
                Schedule.objects.get_or_create(
                    bus=bus,
                    route=route,
                    departure_time=departure_time,
                    defaults={
                        'arrival_time': arrival_time,
                        'price': route.price,  # Use route's current price
                        'is_available': True
                    }
                )
        
        # Refresh the schedules query
        schedules = Schedule.objects.select_related('bus', 'route').filter(
            departure_time__gte=timezone.now(),
            is_available=True
        ).order_by('departure_time')
    
    context = {
        'schedules': schedules,
        'all_routes': all_routes,
        'from_location': from_location,
        'to_location': to_location,
        'date': date,
    }
    return render(request, 'NelsaApp/booking.html', context)

def book_success(request):
    # Get the most recent booking for the current user
    if request.user.is_authenticated:
        booking = Booking.objects.filter(passenger__email=request.user.email).order_by('-booking_date').first()
    else:
        booking = None
    
    return render(request, 'NelsaApp/booking_success.html', {'booking': booking})

def seat_booking(request, bus_id):
    bus = get_object_or_404(Bus, id=bus_id)
    seats = bus.seats.all()
    
    if request.method == 'POST':
        seat_id = request.POST.get('seat_id')
        user_name = request.POST.get('user_name')
        
        if seat_id and user_name:
            seat = Seat.objects.get(id=seat_id)
            if not seat.is_booked:
                seat.is_booked = True
                seat.save()
                Booking.objects.create(user_name=user_name, seat=seat)
                return redirect('seat_booking', bus_id=bus.id)
    
   

def seat_booking(request):
    """Render seat booking page with available seats."""
    seats = Seat.objects.all()
    return render(request, "seat_booking.html", {"seats": seats})

@csrf_exempt  # Use only if you have CSRF issues (better to use middleware token)
def book_seat(request):
    """Handles seat booking via AJAX request."""
    if request.method == "POST":
        row = request.POST.get("row")
        column = request.POST.get("column")

        try:
            seat = Seat.objects.get(row=row, column=column)
            
            if seat.is_booked:
                return JsonResponse({"success": False, "message": "Seat is already booked."})
            
            seat.is_booked = True
            seat.save()

            return JsonResponse({"success": True, "message": "Seat booked successfully!"})
        
        except Seat.DoesNotExist:
            return JsonResponse({"success": False, "message": "Invalid seat selection."})

    return JsonResponse({"success": False, "message": "Invalid request."}, status=400)

# Admin view
@login_required
def admin_view(request):
    # Check if user is admin
    if not request.user.is_staff:
        return redirect('home')
    
    # Get statistics for the dashboard
    total_buses = Bus.objects.count()
    total_bookings = Booking.objects.count()
    
    # User statistics
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    inactive_users = User.objects.filter(is_active=False).count()
    staff_users = User.objects.filter(is_staff=True).count()
    superusers = User.objects.filter(is_superuser=True).count()
    
    # Calculate total revenue by summing up the prices from schedules associated with bookings
    total_revenue = sum(booking.schedule.price for booking in Booking.objects.select_related('schedule').all())
    
    context = {
        'total_buses': total_buses,
        'total_bookings': total_bookings,
        'total_users': total_users,
        'active_users': active_users,
        'inactive_users': inactive_users,
        'staff_users': staff_users,
        'superusers': superusers,
        'total_revenue': total_revenue,
    }
    
    return render(request, 'NelsaApp/admin.html', context)

# New views for booking functionality

@login_required
def get_seats(request, schedule_id):
    """API endpoint to get seats for a specific schedule."""
    schedule = get_object_or_404(Schedule, id=schedule_id)
    bus = schedule.bus
    
    # Get all seats for this bus
    seats = []
    for i in range(1, bus.capacity + 1):
        # Check if this seat is already booked for this schedule
        is_booked = Booking.objects.filter(schedule=schedule, seat_number=i).exists()
        
        seats.append({
            'id': i,
            'seat_number': i,
            'is_booked': is_booked
        })
    
    return JsonResponse({'seats': seats})

@login_required
def book_seats_api(request):
    """API endpoint to book seats."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'})
    
    try:
        data = json.loads(request.body)
        schedule_id = data.get('schedule_id')
        seat_ids = data.get('seat_ids', [])
        
        if not schedule_id or not seat_ids:
            return JsonResponse({'success': False, 'message': 'Missing required data'})
        
        schedule = get_object_or_404(Schedule, id=schedule_id)
        
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'message': 'You must be logged in to book seats'})
        
        # Get or create passenger with unique identification
        # Use a combination of user info to ensure uniqueness
        user_display_name = request.user.get_full_name()
        if not user_display_name or user_display_name.strip() == '':
            # If no full name, create a unique display name using username and user ID
            user_display_name = f"{request.user.username} (ID: {request.user.id})"
        
        passenger, created = Passenger.objects.get_or_create(
            email=request.user.email,
            defaults={
                'name': user_display_name,
                'phone': 'N/A'  # You might want to collect this during registration
            }
        )
        
        # If passenger already exists but name is generic, update it with unique identifier
        if not created and (passenger.name == request.user.username or 
                          passenger.name == 'Doh Derick' or 
                          passenger.name == 'N/A'):
            passenger.name = f"{request.user.username} (ID: {request.user.id})"
            passenger.save()
        
        # Check if any seat is already booked
        for seat_id in seat_ids:
            if Booking.objects.filter(schedule=schedule, seat_number=seat_id).exists():
                return JsonResponse({'success': False, 'message': f'Seat {seat_id} is already booked'})
        
        # Calculate total amount
        total_amount = schedule.price * len(seat_ids)
        
        # Create BookingGroup
        booking_group = BookingGroup.objects.create(
            passenger=passenger,
            schedule=schedule,
            total_amount=total_amount,
            status='Pending'
        )
        
        # Create bookings for each seat and link to group
        bookings = []
        for seat_id in seat_ids:
            booking = Booking.objects.create(
                passenger=passenger,
                schedule=schedule,
                seat_number=seat_id,
                status='Pending',
                booking_group=booking_group
            )
            bookings.append(booking)
        
        # Return success with the booking group ID to redirect to payment
        return JsonResponse({
            'success': True, 
            'message': 'Booking successful',
            'booking_group_id': booking_group.id
        })
    
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@login_required
def booking_success_view(request):
    """View for the booking success page."""
    # Get the most recent booking for the current user
    if request.user.is_authenticated:
        booking = Booking.objects.filter(passenger__email=request.user.email).order_by('-booking_date').first()
    else:
        booking = None
    
    return render(request, 'NelsaApp/booking_success.html', {'booking': booking})

# Admin booking management views
@login_required
def admin_bookings(request):
    """Admin view to manage all bookings organized by customer."""
    # Check if user is admin
    if not request.user.is_staff:
        return redirect('index')
    
    # Get filter parameters
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    from_date = request.GET.get('from_date', '')
    to_date = request.GET.get('to_date', '')
    customer_filter = request.GET.get('customer', '')
    
    # Base query - get booking groups with passenger info
    booking_groups = BookingGroup.objects.select_related('passenger', 'schedule__route', 'schedule__bus').all()
    
    # Apply search filter
    if search_query:
        booking_groups = booking_groups.filter(
            Q(passenger__name__icontains=search_query) |
            Q(passenger__email__icontains=search_query) |
            Q(schedule__route__start_location__icontains=search_query) |
            Q(schedule__route__end_location__icontains=search_query) |
            Q(schedule__bus__bus_number__icontains=search_query) |
            Q(id__icontains=search_query)
        )
    
    # Apply status filter
    if status_filter:
        booking_groups = booking_groups.filter(status=status_filter)
    
    # Apply customer filter
    if customer_filter:
        booking_groups = booking_groups.filter(passenger__email=customer_filter)
    
    # Apply date filters
    if from_date:
        try:
            from_date_obj = datetime.strptime(from_date, '%Y-%m-%d').date()
            booking_groups = booking_groups.filter(schedule__departure_time__date__gte=from_date_obj)
        except ValueError:
            pass
    
    if to_date:
        try:
            to_date_obj = datetime.strptime(to_date, '%Y-%m-%d').date()
            booking_groups = booking_groups.filter(schedule__departure_time__date__lte=to_date_obj)
        except ValueError:
            pass
    
    # Order by creation date (newest first)
    booking_groups = booking_groups.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(booking_groups, 15)  # Show 15 booking groups per page
    page = request.GET.get('page')
    booking_groups = paginator.get_page(page)
    
    # Get booking statistics
    total_bookings = BookingGroup.objects.count()
    confirmed_bookings = BookingGroup.objects.filter(status='Confirmed').count()
    pending_bookings = BookingGroup.objects.filter(status='Pending').count()
    cancelled_bookings = BookingGroup.objects.filter(status='Cancelled').count()
    
    # Get unique customers for filter dropdown
    customers = Passenger.objects.filter(
        bookinggroup__isnull=False
    ).distinct().order_by('name')
    
    context = {
        'booking_groups': booking_groups,
        'total_bookings': total_bookings,
        'confirmed_bookings': confirmed_bookings,
        'pending_bookings': pending_bookings,
        'cancelled_bookings': cancelled_bookings,
        'customers': customers,
        'search_query': search_query,
        'status_filter': status_filter,
        'from_date': from_date,
        'to_date': to_date,
        'customer_filter': customer_filter,
    }
    
    return render(request, 'NelsaApp/admin_bookings.html', context)

@login_required
def admin_booking_detail(request, booking_group_id):
    """Admin view to see booking group details."""
    # Check if user is admin
    if not request.user.is_staff:
        return redirect('index')
    
    booking_group = get_object_or_404(BookingGroup, id=booking_group_id)
    
    return render(request, 'NelsaApp/admin_booking_detail.html', {'booking_group': booking_group})

@login_required
def admin_confirm_booking(request, booking_group_id):
    """Admin view to confirm a booking group only if transaction is verified."""
    if not request.user.is_staff:
        return redirect('index')
    
    booking_group = get_object_or_404(BookingGroup, id=booking_group_id)
    
    if booking_group.status == 'Pending':
        if not booking_group.transaction_verified or not booking_group.transaction_id:
            messages.error(request, 'Cannot confirm booking. Please verify a valid transaction ID first.')
            return redirect('admin_booking_detail', booking_group_id=booking_group.id)
        
        # Update booking status
        booking_group.bookings.update(status='Confirmed')
        booking_group.status = 'Confirmed'
        booking_group.save()
        
        # SMS functionality disabled
        messages.success(request, f'Booking Group #{booking_group.id} has been confirmed.')
    else:
        messages.error(request, f'Booking Group #{booking_group.id} cannot be confirmed because it is not in Pending status.')
    
    return redirect('admin_bookings')

@login_required
def admin_cancel_booking(request, booking_group_id):
    """Admin view to cancel a booking group."""
    if not request.user.is_staff:
        return redirect('index')
    
    booking_group = get_object_or_404(BookingGroup, id=booking_group_id)
    
    if booking_group.status != 'Cancelled':
        # Update booking status
        booking_group.bookings.update(status='Cancelled')
        booking_group.status = 'Cancelled'
        booking_group.save()
        
        # SMS functionality disabled
        messages.success(request, f'Booking Group #{booking_group.id} has been cancelled.')
    else:
        messages.error(request, f'Booking Group #{booking_group.id} is already cancelled.')
    
    return redirect('admin_bookings')

@login_required
def user_profile(request):
    """View for the user profile page."""
    # Get search parameters
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    date_filter = request.GET.get('date', '')
    
    # Get the user's booking groups
    booking_groups = BookingGroup.objects.filter(passenger__email=request.user.email)
    
    # Apply search filter
    if search_query:
        booking_groups = booking_groups.filter(
            Q(schedule__route__start_location__icontains=search_query) |
            Q(schedule__route__end_location__icontains=search_query) |
            Q(schedule__bus__bus_number__icontains=search_query) |
            Q(id__icontains=search_query)
        )
    
    # Apply status filter
    if status_filter:
        booking_groups = booking_groups.filter(status=status_filter)
    
    # Apply date filter
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            booking_groups = booking_groups.filter(schedule__departure_time__date=filter_date)
        except ValueError:
            pass
    
    # Order by creation date (newest first)
    booking_groups = booking_groups.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(booking_groups, 10)  # Show 10 booking groups per page
    page = request.GET.get('page')
    booking_groups = paginator.get_page(page)
    
    # Get booking statistics for the user
    total_bookings = BookingGroup.objects.filter(passenger__email=request.user.email).count()
    confirmed_bookings = BookingGroup.objects.filter(passenger__email=request.user.email, status='Confirmed').count()
    pending_bookings = BookingGroup.objects.filter(passenger__email=request.user.email, status='Pending').count()
    cancelled_bookings = BookingGroup.objects.filter(passenger__email=request.user.email, status='Cancelled').count()
    
    context = {
        'booking_groups': booking_groups,
        'total_bookings': total_bookings,
        'confirmed_bookings': confirmed_bookings,
        'pending_bookings': pending_bookings,
        'cancelled_bookings': cancelled_bookings,
        'search_query': search_query,
        'status_filter': status_filter,
        'date_filter': date_filter,
    }
    
    return render(request, 'NelsaApp/user_profile.html', context)

@login_required
def profile_edit(request):
    """View for editing user profile information."""
    # Get the user's passenger profile or create one if it doesn't exist
    passenger, created = Passenger.objects.get_or_create(
        email=request.user.email,
        defaults={
            'name': request.user.get_full_name() or request.user.username,
            'phone': ''
        }
    )
    
    if request.method == 'POST':
        # Update passenger information
        passenger.name = request.POST.get('name', passenger.name)
        passenger.phone = request.POST.get('phone', passenger.phone)
        passenger.save()
        
        # Update user information
        user = request.user
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.save()
        
        messages.success(request, 'Your profile has been updated successfully!')
        return redirect('user_profile')
    
    context = {
        'passenger': passenger,
        'user': request.user
    }
    
    return render(request, 'NelsaApp/profile_edit.html', context)

def routes_page(request):
    """
    View function for displaying available routes and schedules.
    """
    # Get all routes with their schedules
    routes = Route.objects.all().prefetch_related('schedules')
    
    # Add additional route information
    for route in routes:
        # Get the next available schedule
        next_schedule = route.schedules.filter(departure_time__gt=timezone.now()).order_by('departure_time').first()
        
        # Calculate daily departures
        daily_departures = route.schedules.filter(
            departure_time__date=timezone.now().date()
        ).count()
        
        # Add the information to the route object
        route.next_schedule = next_schedule
        route.daily_departures = daily_departures
        
        # Format departure times for display
        departure_times = route.schedules.filter(
            departure_time__date=timezone.now().date()
        ).order_by('departure_time').values_list('departure_time', flat=True)
        
        route.formatted_departure_times = ', '.join(
            [time.strftime('%I:%M %p') for time in departure_times]
        )
    
    context = {
        'routes': routes,
    }
    
    return render(request, 'NelsaApp/routes.html', context)

def contact_page(request):
    """
    View function for the contact page.
    """
    if request.method == 'POST':
        # Process form submission
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        # Save the contact form data to the Support model
        Support.objects.create(
            name=name,
            email=email,
            phone=phone,
            subject=subject,
            message=message,
            status='OPEN',
            priority='MEDIUM',
        )
        
        messages.success(request, 'Thank you for your message! We will get back to you soon.')
        return redirect('contact')
    
    return render(request, 'NelsaApp/contact.html')

def services_page(request):
    """
    View function for the services page.
    """
    return render(request, 'NelsaApp/services.html')

@login_required
@user_passes_test(lambda u: u.is_staff)
def fix_duplicate_passengers(request):
    """Fix passengers with duplicate or generic names."""
    if request.method == 'POST':
        # Get all passengers with generic names
        generic_passengers = Passenger.objects.filter(
            name__in=['Doh Derick', 'N/A', '']).exclude(email='')
        
        fixed_count = 0
        for passenger in generic_passengers:
            try:
                # Try to find the associated user
                user = User.objects.get(email=passenger.email)
                # Update with unique identifier
                passenger.name = f"{user.username} (ID: {user.id})"
                passenger.save()
                fixed_count += 1
            except User.DoesNotExist:
                # If no user found, use email as identifier
                passenger.name = f"User {passenger.email}"
                passenger.save()
                fixed_count += 1
        
        messages.success(request, f'Fixed {fixed_count} passenger records.')
        return redirect('admin_bookings')
    
    # Get statistics
    total_passengers = Passenger.objects.count()
    generic_passengers = Passenger.objects.filter(
        name__in=['Doh Derick', 'N/A', '']).count()
    duplicate_names = Passenger.objects.values('name').annotate(
        count=Count('name')).filter(count__gt=1).count()
    
    context = {
        'total_passengers': total_passengers,
        'generic_passengers': generic_passengers,
        'duplicate_names': duplicate_names,
    }
    
    return render(request, 'NelsaApp/fix_passengers.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def admin_users(request):
    # Handle user actions
    if request.method == 'POST':
        action = request.POST.get('action')
        user_id = request.POST.get('user_id')
        
        if action and user_id:
            try:
                user = User.objects.get(id=user_id)
                if action == 'activate':
                    user.is_active = True
                    user.save()
                    messages.success(request, f'User {user.username} has been activated.')
                elif action == 'deactivate':
                    user.is_active = False
                    user.save()
                    messages.success(request, f'User {user.username} has been deactivated.')
                elif action == 'make_staff':
                    user.is_staff = True
                    user.save()
                    messages.success(request, f'User {user.username} has been made staff.')
                elif action == 'remove_staff':
                    user.is_staff = False
                    user.save()
                    messages.success(request, f'User {user.username} is no longer staff.')
            except User.DoesNotExist:
                messages.error(request, 'User not found.')
    
    # Get search and filter parameters
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    role_filter = request.GET.get('role', '')
    
    # Build queryset with filters
    users = User.objects.all()
    
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )
    
    if status_filter:
        if status_filter == 'active':
            users = users.filter(is_active=True)
        elif status_filter == 'inactive':
            users = users.filter(is_active=False)
    
    if role_filter:
        if role_filter == 'staff':
            users = users.filter(is_staff=True)
        elif role_filter == 'user':
            users = users.filter(is_staff=False)
    
    # Order by date joined (newest first)
    users = users.order_by('-date_joined')
    
    # Pagination
    paginator = Paginator(users, 15)  # Show 15 users per page
    page = request.GET.get('page')
    users = paginator.get_page(page)
    
    # Get user statistics
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    staff_users = User.objects.filter(is_staff=True).count()
    inactive_users = User.objects.filter(is_active=False).count()
    
    context = {
        'users': users,
        'total_users': total_users,
        'active_users': active_users,
        'staff_users': staff_users,
        'inactive_users': inactive_users,
        'search_query': search_query,
        'status_filter': status_filter,
        'role_filter': role_filter,
    }
    
    return render(request, 'NelsaApp/admin_users.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def admin_user_detail(request, user_id):
    """View detailed information about a specific user."""
    user = get_object_or_404(User, id=user_id)
    
    # Get user's bookings
    try:
        passenger = Passenger.objects.get(email=user.email)
        bookings = Booking.objects.filter(passenger=passenger).select_related('schedule', 'schedule__bus', 'schedule__route').order_by('-booking_date')
    except Passenger.DoesNotExist:
        bookings = []
    
    # Get user statistics
    total_bookings = len(bookings)
    confirmed_bookings = len([b for b in bookings if b.status == 'Confirmed'])
    cancelled_bookings = len([b for b in bookings if b.status == 'Cancelled'])
    
    context = {
        'user_detail': user,
        'bookings': bookings[:10],  # Show only last 10 bookings
        'total_bookings': total_bookings,
        'confirmed_bookings': confirmed_bookings,
        'cancelled_bookings': cancelled_bookings,
    }
    
    return render(request, 'NelsaApp/admin_user_detail.html', context)

@login_required
def payment_page(request, booking_group_id):
    """View for selecting payment method for a group of bookings."""
    booking_group = get_object_or_404(BookingGroup, id=booking_group_id, passenger__email=request.user.email)
    
    # Check if booking group already has a payment
    if hasattr(booking_group, 'payment') and booking_group.payment.status == 'COMPLETED':
        messages.info(request, 'Payment for this booking has already been completed.')
        return redirect('booking_success')
    
    return render(request, 'NelsaApp/payment.html', {'booking_group': booking_group})

@login_required
def process_payment(request, payment_method, booking_group_id):
    """View for processing payment with the selected method for a group of bookings."""
    booking_group = get_object_or_404(BookingGroup, id=booking_group_id, passenger__email=request.user.email)
    
    # Check if booking group already has a payment
    if hasattr(booking_group, 'payment') and booking_group.payment.status == 'COMPLETED':
        messages.info(request, 'Payment for this booking has already been completed.')
        return redirect('booking_success')
    
    # Validate payment method
    valid_methods = [method[0] for method in Payment.PAYMENT_METHODS]
    if payment_method not in valid_methods:
        messages.error(request, 'Invalid payment method selected.')
        return redirect('payment', booking_group_id=booking_group_id)
    
    return render(request, 'NelsaApp/payment_processing.html', {
        'booking_group': booking_group,
        'payment_method': payment_method
    })

@login_required
def verify_payment(request):
    """API endpoint to verify payment for a booking group."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'})
    
    try:
        data = json.loads(request.body)
        booking_group_id = data.get('booking_group_id')
        payment_method = data.get('payment_method')
        transaction_id = data.get('transaction_id')
        
        if not all([booking_group_id, payment_method, transaction_id]):
            return JsonResponse({'success': False, 'message': 'Missing required data'})
        
        booking_group = get_object_or_404(BookingGroup, id=booking_group_id, passenger__email=request.user.email)
        
        # In a real application, you would verify the transaction with the payment provider
        # For this demo, we'll just create a payment record
        payment, created = Payment.objects.get_or_create(
            booking_group=booking_group,
            defaults={
                'amount': booking_group.total_amount,
                'payment_method': payment_method,
                'transaction_id': transaction_id,
                'status': 'COMPLETED',
                'payment_details': {
                    'verified_at': timezone.now().isoformat(),
                    'verified_by': request.user.username
                }
            }
        )
        
        if not created:
            payment.transaction_id = transaction_id
            payment.status = 'COMPLETED'
            payment.payment_details = {
                'verified_at': timezone.now().isoformat(),
                'verified_by': request.user.username
            }
            payment.save()
        
        # Update all bookings in the group to confirmed
        booking_group.bookings.update(status='Confirmed')
        booking_group.status = 'Confirmed'
        booking_group.save()
        
        return JsonResponse({'success': True, 'message': 'Payment verified successfully'})
    
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@login_required
@user_passes_test(lambda u: u.is_staff)
def admin_reports(request):
    """Admin view for generating and viewing system reports."""
    # Get report type and date range from request
    report_type = request.GET.get('type', 'revenue')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Calculate date range
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
        except ValueError:
            from_date = None
    else:
        from_date = None
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
        except ValueError:
            to_date = None
    else:
        to_date = None
    
    # Generate reports based on type
    if report_type == 'bookings':
        report_data = generate_booking_report(from_date, to_date)
    elif report_type == 'revenue':
        report_data = generate_revenue_report(from_date, to_date)
    elif report_type == 'buses':
        report_data = generate_bus_report(from_date, to_date)
    else:
        report_data = generate_revenue_report(from_date, to_date)
    
    context = {
        'report_type': report_type,
        'date_from': date_from,
        'date_to': date_to,
        'report_data': report_data,
    }
    
    return render(request, 'NelsaApp/admin_reports.html', context)

def generate_user_report(from_date=None, to_date=None):
    """Generate user registration and activity report."""
    users = User.objects.all()
    
    if from_date:
        users = users.filter(date_joined__date__gte=from_date)
    if to_date:
        users = users.filter(date_joined__date__lte=to_date)
    
    # User registration trends (last 30 days)
    thirty_days_ago = timezone.now().date() - timedelta(days=30)
    daily_registrations = []
    for i in range(30):
        date = thirty_days_ago + timedelta(days=i)
        count = User.objects.filter(date_joined__date=date).count()
        daily_registrations.append({
            'date': date.strftime('%Y-%m-%d'),
            'count': count
        })
    
    # User statistics
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    staff_users = User.objects.filter(is_staff=True).count()
    new_users_this_month = User.objects.filter(date_joined__month=timezone.now().month).count()
    new_users_this_week = User.objects.filter(date_joined__gte=timezone.now() - timedelta(days=7)).count()
    
    # Top users by booking count
    top_users = []
    for user in users[:10]:  # Top 10 users
        try:
            passenger = Passenger.objects.get(email=user.email)
            booking_count = Booking.objects.filter(passenger=passenger).count()
            if booking_count > 0:
                top_users.append({
                    'user': user,
                    'booking_count': booking_count,
                    'last_booking': Booking.objects.filter(passenger=passenger).order_by('-booking_date').first()
                })
        except Passenger.DoesNotExist:
            continue
    
    # Sort by booking count
    top_users.sort(key=lambda x: x['booking_count'], reverse=True)
    
    return {
        'total_users': total_users,
        'active_users': active_users,
        'staff_users': staff_users,
        'new_users_this_month': new_users_this_month,
        'new_users_this_week': new_users_this_week,
        'daily_registrations': daily_registrations,
        'top_users': top_users[:5],  # Top 5 users
        'users_in_period': users.count(),
    }

def generate_booking_report(from_date=None, to_date=None):
    """Generate booking statistics report."""
    bookings = Booking.objects.all()
    
    if from_date:
        bookings = bookings.filter(booking_date__date__gte=from_date)
    if to_date:
        bookings = bookings.filter(booking_date__date__lte=to_date)
    
    # Booking statistics
    total_bookings = Booking.objects.count()
    confirmed_bookings = Booking.objects.filter(status='Confirmed').count()
    pending_bookings = Booking.objects.filter(status='Pending').count()
    cancelled_bookings = Booking.objects.filter(status='Cancelled').count()
    
    # Bookings in period
    bookings_in_period = bookings.count()
    confirmed_in_period = bookings.filter(status='Confirmed').count()
    pending_in_period = bookings.filter(status='Pending').count()
    cancelled_in_period = bookings.filter(status='Cancelled').count()
    
    # Popular routes
    popular_routes = []
    route_bookings = {}
    for booking in bookings.select_related('schedule__route'):
        route_key = f"{booking.schedule.route.start_location} → {booking.schedule.route.end_location}"
        if route_key in route_bookings:
            route_bookings[route_key] += 1
        else:
            route_bookings[route_key] = 1
    
    for route, count in sorted(route_bookings.items(), key=lambda x: x[1], reverse=True)[:5]:
        popular_routes.append({'route': route, 'count': count})
    
    # Daily booking trends (last 30 days)
    thirty_days_ago = timezone.now().date() - timedelta(days=30)
    daily_bookings = []
    for i in range(30):
        date = thirty_days_ago + timedelta(days=i)
        count = Booking.objects.filter(booking_date__date=date).count()
        daily_bookings.append({
            'date': date.strftime('%Y-%m-%d'),
            'count': count
        })
    
    return {
        'total_bookings': total_bookings,
        'confirmed_bookings': confirmed_bookings,
        'pending_bookings': pending_bookings,
        'cancelled_bookings': cancelled_bookings,
        'bookings_in_period': bookings_in_period,
        'confirmed_in_period': confirmed_in_period,
        'pending_in_period': pending_in_period,
        'cancelled_in_period': cancelled_in_period,
        'popular_routes': popular_routes,
        'daily_bookings': daily_bookings,
    }

def generate_revenue_report(from_date=None, to_date=None):
    """Generate revenue and financial report with daily breakdown."""
    bookings = Booking.objects.filter(status='Confirmed').select_related('schedule', 'schedule__bus', 'schedule__route', 'passenger')
    
    if from_date:
        bookings = bookings.filter(booking_date__date__gte=from_date)
    if to_date:
        bookings = bookings.filter(booking_date__date__lte=to_date)
    
    # Revenue calculations
    total_revenue = sum(booking.schedule.price for booking in bookings)
    total_revenue_all_time = sum(booking.schedule.price for booking in Booking.objects.filter(status='Confirmed').select_related('schedule'))
    bookings_count = bookings.count()
    
    # Calculate average revenue per booking
    avg_revenue_per_booking = total_revenue / bookings_count if bookings_count > 0 else 0
    
    # Daily revenue breakdown with passenger and bus information
    daily_revenue = {}
    for booking in bookings:
        booking_date = booking.booking_date.date()
        if booking_date not in daily_revenue:
            daily_revenue[booking_date] = {
                'date': booking_date,
                'total_revenue': 0,
                'bookings': [],
                'passenger_count': 0
            }
        
        daily_revenue[booking_date]['total_revenue'] += booking.schedule.price
        daily_revenue[booking_date]['passenger_count'] += 1
        
        # Add detailed booking information
        daily_revenue[booking_date]['bookings'].append({
            'passenger_name': booking.passenger.name,
            'passenger_email': booking.passenger.email,
            'bus_number': booking.schedule.bus.bus_number,
            'bus_type': booking.schedule.bus.bus_type,
            'route': f"{booking.schedule.route.start_location} → {booking.schedule.route.end_location}",
            'amount': booking.schedule.price,
            'booking_time': booking.booking_date.strftime('%H:%M'),
            'seat_number': booking.seat_number
        })
    
    # Sort daily revenue by date (newest first)
    daily_revenue_list = sorted(daily_revenue.values(), key=lambda x: x['date'], reverse=True)
    
    # Revenue by route
    route_revenue = {}
    for booking in bookings:
        route_key = f"{booking.schedule.route.start_location} → {booking.schedule.route.end_location}"
        if route_key in route_revenue:
            route_revenue[route_key] += booking.schedule.price
        else:
            route_revenue[route_key] = booking.schedule.price
    
    top_routes_by_revenue = []
    for route, revenue in sorted(route_revenue.items(), key=lambda x: x[1], reverse=True)[:5]:
        top_routes_by_revenue.append({'route': route, 'revenue': revenue})
    
    # Revenue by bus type
    bus_type_revenue = {}
    for booking in bookings:
        bus_type = booking.schedule.bus.bus_type
        if bus_type in bus_type_revenue:
            bus_type_revenue[bus_type] += booking.schedule.price
        else:
            bus_type_revenue[bus_type] = booking.schedule.price
    
    # Monthly revenue (last 12 months)
    monthly_revenue = []
    for i in range(12):
        month_start = timezone.now().replace(day=1) - timedelta(days=30*i)
        month_end = month_start.replace(day=28) + timedelta(days=4)
        month_end = month_end.replace(day=1) - timedelta(days=1)
        
        month_bookings = Booking.objects.filter(
            status='Confirmed',
            booking_date__date__gte=month_start.date(),
            booking_date__date__lte=month_end.date()
        ).select_related('schedule')
        
        revenue = sum(booking.schedule.price for booking in month_bookings)
        monthly_revenue.append({
            'month': month_start.strftime('%Y-%m'),
            'revenue': revenue,
            'revenue_in_k': revenue / 1000  # Revenue in thousands
        })
    
    # Generate report date automatically
    report_generated_date = timezone.now().strftime('%B %d, %Y at %I:%M %p')
    
    return {
        'total_revenue': total_revenue,
        'total_revenue_all_time': total_revenue_all_time,
        'avg_revenue_per_booking': avg_revenue_per_booking,
        'top_routes_by_revenue': top_routes_by_revenue,
        'bus_type_revenue': bus_type_revenue,
        'monthly_revenue': monthly_revenue,
        'bookings_count': bookings_count,
        'daily_revenue': daily_revenue_list,
        'report_generated_date': report_generated_date,
    }

def generate_bus_report(from_date=None, to_date=None):
    """Generate bus utilization and performance report."""
    buses = Bus.objects.all()
    
    # Bus statistics
    total_buses = buses.count()
    available_buses = buses.filter(is_available=True).count()
    luxury_buses = buses.filter(bus_type='Luxury').count()
    standard_buses = buses.filter(bus_type='Standard').count()
    express_buses = buses.filter(bus_type='Express').count()
    
    # Bus utilization
    bus_utilization = []
    for bus in buses:
        # Count bookings for this bus
        bookings_count = Booking.objects.filter(schedule__bus=bus).count()
        # Calculate utilization percentage (assuming average 2 trips per day)
        utilization_percentage = min((bookings_count / 60) * 100, 100)  # 60 = 2 trips * 30 days
        
        bus_utilization.append({
            'bus': bus,
            'bookings_count': bookings_count,
            'utilization_percentage': round(utilization_percentage, 1)
        })
    
    # Sort by utilization
    bus_utilization.sort(key=lambda x: x['utilization_percentage'], reverse=True)
    
    # Popular bus types
    bus_type_stats = {
        'Luxury': {'count': luxury_buses, 'bookings': 0},
        'Standard': {'count': standard_buses, 'bookings': 0},
        'Express': {'count': express_buses, 'bookings': 0}
    }
    
    for booking in Booking.objects.select_related('schedule__bus'):
        bus_type = booking.schedule.bus.bus_type
        if bus_type in bus_type_stats:
            bus_type_stats[bus_type]['bookings'] += 1
    
    # Calculate average bookings per bus type
    for bus_type, stats in bus_type_stats.items():
        if stats['count'] > 0:
            stats['avg_bookings'] = stats['bookings'] / stats['count']
        else:
            stats['avg_bookings'] = 0
    
    return {
        'total_buses': total_buses,
        'available_buses': available_buses,
        'luxury_buses': luxury_buses,
        'standard_buses': standard_buses,
        'express_buses': express_buses,
        'bus_utilization': bus_utilization[:10],  # Top 10 buses
        'bus_type_stats': bus_type_stats,
    }

@login_required
@user_passes_test(lambda u: u.is_staff)
def admin_buses(request):
    """Admin view for managing buses."""
    # Handle bus actions
    if request.method == 'POST':
        action = request.POST.get('action')
        bus_id = request.POST.get('bus_id')
        
        if action and bus_id:
            try:
                bus = Bus.objects.get(id=bus_id)
                if action == 'activate':
                    bus.is_available = True
                    bus.save()
                    messages.success(request, f'Bus {bus.bus_number} has been activated.')
                elif action == 'deactivate':
                    bus.is_available = False
                    bus.save()
                    messages.success(request, f'Bus {bus.bus_number} has been deactivated.')
                elif action == 'delete':
                    # Check if bus has any bookings
                    if not Schedule.objects.filter(bus=bus).exists():
                        bus.delete()
                        messages.success(request, f'Bus {bus.bus_number} has been deleted.')
                    else:
                        messages.error(request, f'Cannot delete bus {bus.bus_number} - it has associated schedules.')
            except Bus.DoesNotExist:
                messages.error(request, 'Bus not found.')
    
    # Get search and filter parameters
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    type_filter = request.GET.get('type', '')
    
    # Build queryset with filters
    buses = Bus.objects.all()
    
    if search_query:
        buses = buses.filter(
            Q(bus_number__icontains=search_query) |
            Q(bus_type__icontains=search_query) |
            Q(operator__icontains=search_query)
        )
    
    if status_filter:
        if status_filter == 'available':
            buses = buses.filter(is_available=True)
        elif status_filter == 'unavailable':
            buses = buses.filter(is_available=False)
    
    if type_filter:
        buses = buses.filter(bus_type=type_filter)
    
    # Order by bus number
    buses = buses.order_by('bus_number')
    
    # Pagination
    paginator = Paginator(buses, 10)  # Show 10 buses per page
    page = request.GET.get('page')
    buses = paginator.get_page(page)
    
    # Get bus statistics
    total_buses = Bus.objects.count()
    available_buses = Bus.objects.filter(is_available=True).count()
    unavailable_buses = Bus.objects.filter(is_available=False).count()
    luxury_buses = Bus.objects.filter(bus_type='Luxury').count()
    standard_buses = Bus.objects.filter(bus_type='Standard').count()
    express_buses = Bus.objects.filter(bus_type='Express').count()
    
    context = {
        'buses': buses,
        'total_buses': total_buses,
        'available_buses': available_buses,
        'unavailable_buses': unavailable_buses,
        'luxury_buses': luxury_buses,
        'standard_buses': standard_buses,
        'express_buses': express_buses,
        'search_query': search_query,
        'status_filter': status_filter,
        'type_filter': type_filter,
    }
    
    return render(request, 'NelsaApp/admin_buses.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def admin_bus_detail(request, bus_id):
    """View detailed information about a specific bus."""
    bus = get_object_or_404(Bus, id=bus_id)
    
    # Get bus schedules
    schedules = Schedule.objects.filter(bus=bus).select_related('route').order_by('-departure_time')
    
    # Get bus statistics
    total_schedules = schedules.count()
    upcoming_schedules = schedules.filter(departure_time__gte=timezone.now()).count()
    past_schedules = schedules.filter(departure_time__lt=timezone.now()).count()
    
    # Get bookings for this bus
    bookings = Booking.objects.filter(schedule__bus=bus).select_related('passenger', 'schedule__route').order_by('-booking_date')
    total_bookings = bookings.count()
    confirmed_bookings = bookings.filter(status='Confirmed').count()
    
    # Calculate utilization
    utilization_percentage = min((total_bookings / 60) * 100, 100) if total_bookings > 0 else 0
    
    context = {
        'bus_detail': bus,
        'schedules': schedules[:10],  # Show only last 10 schedules
        'bookings': bookings[:10],    # Show only last 10 bookings
        'total_schedules': total_schedules,
        'upcoming_schedules': upcoming_schedules,
        'past_schedules': past_schedules,
        'total_bookings': total_bookings,
        'confirmed_bookings': confirmed_bookings,
        'utilization_percentage': round(utilization_percentage, 1),
    }
    
    return render(request, 'NelsaApp/admin_bus_detail.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def admin_bus_add(request):
    """Add a new bus."""
    if request.method == 'POST':
        bus_number = request.POST.get('bus_number')
        bus_type = request.POST.get('bus_type')
        capacity = request.POST.get('capacity')
        operator = request.POST.get('operator')
        is_available = request.POST.get('is_available') == 'on'
        
        # Validate required fields
        if not all([bus_number, bus_type, capacity]):
            messages.error(request, 'Please fill in all required fields.')
        else:
            try:
                capacity = int(capacity)
                if capacity <= 0:
                    messages.error(request, 'Capacity must be a positive number.')
                else:
                    # Check if bus number already exists
                    if Bus.objects.filter(bus_number=bus_number).exists():
                        messages.error(request, f'Bus number {bus_number} already exists.')
                    else:
                        bus = Bus.objects.create(
                            bus_number=bus_number,
                            bus_type=bus_type,
                            capacity=capacity,
                            operator=operator,
                            is_available=is_available
                        )
                        messages.success(request, f'Bus {bus_number} has been added successfully.')
                        return redirect('admin_buses')
            except ValueError:
                messages.error(request, 'Capacity must be a valid number.')
    
    return render(request, 'NelsaApp/admin_bus_add.html')

@login_required
@user_passes_test(lambda u: u.is_staff)
def admin_bus_edit(request, bus_id):
    """Edit an existing bus."""
    bus = get_object_or_404(Bus, id=bus_id)
    
    if request.method == 'POST':
        bus_number = request.POST.get('bus_number')
        bus_type = request.POST.get('bus_type')
        capacity = request.POST.get('capacity')
        operator = request.POST.get('operator')
        is_available = request.POST.get('is_available') == 'on'
        
        # Validate required fields
        if not all([bus_number, bus_type, capacity]):
            messages.error(request, 'Please fill in all required fields.')
        else:
            try:
                capacity = int(capacity)
                if capacity <= 0:
                    messages.error(request, 'Capacity must be a positive number.')
                else:
                    # Check if bus number already exists (excluding current bus)
                    if Bus.objects.filter(bus_number=bus_number).exclude(id=bus.id).exists():
                        messages.error(request, f'Bus number {bus_number} already exists.')
                    else:
                        bus.bus_number = bus_number
                        bus.bus_type = bus_type
                        bus.capacity = capacity
                        bus.operator = operator
                        bus.is_available = is_available
                        bus.save()
                        messages.success(request, f'Bus {bus_number} has been updated successfully.')
                        return redirect('admin_buses')
            except ValueError:
                messages.error(request, 'Capacity must be a valid number.')
    
    context = {
        'bus': bus,
    }
    
    return render(request, 'NelsaApp/admin_bus_edit.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def admin_routes(request):
    """Admin view for managing routes and their prices."""
    # Handle route actions
    if request.method == 'POST':
        action = request.POST.get('action')
        route_id = request.POST.get('route_id')
        
        if action and route_id:
            try:
                route = Route.objects.get(id=route_id)
                if action == 'delete':
                    # Check if route has any schedules
                    if not Schedule.objects.filter(route=route).exists():
                        route.delete()
                        messages.success(request, f'Route {route.start_location} → {route.end_location} has been deleted.')
                    else:
                        messages.error(request, f'Cannot delete route - it has associated schedules.')
            except Route.DoesNotExist:
                messages.error(request, 'Route not found.')
    
    # Get search and filter parameters
    search_query = request.GET.get('search', '')
    from_location = request.GET.get('from_location', '')
    to_location = request.GET.get('to_location', '')
    
    # Build queryset with filters
    routes = Route.objects.all()
    
    if search_query:
        routes = routes.filter(
            Q(start_location__icontains=search_query) |
            Q(end_location__icontains=search_query)
        )
    
    if from_location:
        routes = routes.filter(start_location__icontains=from_location)
    
    if to_location:
        routes = routes.filter(end_location__icontains=to_location)
    
    # Order by start location
    routes = routes.order_by('start_location', 'end_location')
    
    # Pagination
    paginator = Paginator(routes, 10)  # Show 10 routes per page
    page = request.GET.get('page')
    routes = paginator.get_page(page)
    
    # Get route statistics
    total_routes = Route.objects.count()
    total_distance = sum(route.distance for route in Route.objects.all())
    avg_price = sum(route.price for route in Route.objects.all()) / total_routes if total_routes > 0 else 0
    
    # Get popular routes (routes with most schedules)
    popular_routes = []
    route_schedules = {}
    for route in Route.objects.all():
        schedule_count = Schedule.objects.filter(route=route).count()
        if schedule_count > 0:
            route_schedules[route] = schedule_count
    
    # Sort by schedule count and get top 5
    popular_routes = sorted(route_schedules.items(), key=lambda x: x[1], reverse=True)[:5]
    
    context = {
        'routes': routes,
        'total_routes': total_routes,
        'total_distance': round(total_distance, 1),
        'avg_price': round(avg_price, 2),
        'popular_routes': popular_routes,
        'search_query': search_query,
        'from_location': from_location,
        'to_location': to_location,
    }
    
    return render(request, 'NelsaApp/admin_routes.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def admin_route_detail(request, route_id):
    """View detailed information about a specific route."""
    route = get_object_or_404(Route, id=route_id)
    
    # Get route schedules
    schedules = Schedule.objects.filter(route=route).select_related('bus').order_by('-departure_time')
    
    # Get route statistics
    total_schedules = schedules.count()
    upcoming_schedules = schedules.filter(departure_time__gte=timezone.now()).count()
    past_schedules = schedules.filter(departure_time__lt=timezone.now()).count()
    
    # Get bookings for this route
    bookings = Booking.objects.filter(schedule__route=route).select_related('passenger', 'schedule__bus').order_by('-booking_date')
    total_bookings = bookings.count()
    confirmed_bookings = bookings.filter(status='Confirmed').count()
    
    # Calculate revenue
    total_revenue = sum(booking.schedule.price for booking in bookings if booking.status == 'Confirmed')
    
    # Get price history (different prices used in schedules)
    price_history = schedules.values_list('price', flat=True).distinct().order_by('price')
    
    context = {
        'route': route,
        'schedules': schedules[:10],  # Show only last 10 schedules
        'bookings': bookings[:10],    # Show only last 10 bookings
        'total_schedules': total_schedules,
        'upcoming_schedules': upcoming_schedules,
        'past_schedules': past_schedules,
        'total_bookings': total_bookings,
        'confirmed_bookings': confirmed_bookings,
        'total_revenue': total_revenue,
        'price_history': price_history,
    }
    
    return render(request, 'NelsaApp/admin_route_detail.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def admin_route_add(request):
    """Add a new route."""
    if request.method == 'POST':
        start_location = request.POST.get('start_location')
        end_location = request.POST.get('end_location')
        distance = request.POST.get('distance')
        duration = request.POST.get('duration')
        price = request.POST.get('price')
        
        # Validate required fields
        if not all([start_location, end_location, distance, duration, price]):
            messages.error(request, 'Please fill in all required fields.')
        else:
            try:
                distance = float(distance)
                duration = float(duration)
                price = float(price)
                
                if distance <= 0 or duration <= 0 or price < 0:
                    messages.error(request, 'Distance, duration, and price must be positive numbers.')
                else:
                    # Check if route already exists
                    if Route.objects.filter(start_location=start_location, end_location=end_location).exists():
                        messages.error(request, f'Route from {start_location} to {end_location} already exists.')
                    else:
                        # Create the route
                        route = Route.objects.create(
                            start_location=start_location,
                            end_location=end_location,
                            distance=distance,
                            duration=duration,
                            price=price
                        )
                        messages.success(request, f'Route from {start_location} to {end_location} has been added successfully. All schedules will use the route base price.')
                        return redirect('admin_routes')
            except ValueError:
                messages.error(request, 'Distance, duration, and price must be valid numbers.')
    
    return render(request, 'NelsaApp/admin_route_add.html')

@login_required
@user_passes_test(lambda u: u.is_staff)
def admin_route_edit(request, route_id):
    """Edit an existing route."""
    route = get_object_or_404(Route, id=route_id)
    
    if request.method == 'POST':
        start_location = request.POST.get('start_location')
        end_location = request.POST.get('end_location')
        distance = request.POST.get('distance')
        duration = request.POST.get('duration')
        price = request.POST.get('price')
        
        # Validate required fields
        if not all([start_location, end_location, distance, duration, price]):
            messages.error(request, 'Please fill in all required fields.')
        else:
            try:
                distance = float(distance)
                duration = float(duration)
                price = float(price)
                
                if distance <= 0 or duration <= 0 or price < 0:
                    messages.error(request, 'Distance, duration, and price must be positive numbers.')
                else:
                    # Check if route already exists (excluding current route)
                    if Route.objects.filter(start_location=start_location, end_location=end_location).exclude(id=route.id).exists():
                        messages.error(request, f'Route from {start_location} to {end_location} already exists.')
                    else:
                        # Check if price is changing
                        old_price = route.price
                        price_changed = old_price != price
                        
                        route.start_location = start_location
                        route.end_location = end_location
                        route.distance = distance
                        route.duration = duration
                        route.price = price
                        route.save()
                        
                        # Count updated schedules
                        updated_schedules = Schedule.objects.filter(route=route).count()
                        
                        if price_changed and updated_schedules > 0:
                            messages.success(request, f'Route from {start_location} to {end_location} has been updated successfully. {updated_schedules} schedule(s) have been updated with the new price.')
                        else:
                            messages.success(request, f'Route from {start_location} to {end_location} has been updated successfully.')
                        
                        return redirect('admin_routes')
            except ValueError:
                messages.error(request, 'Distance, duration, and price must be valid numbers.')
    
    context = {
        'route': route,
    }
    
    return render(request, 'NelsaApp/admin_route_edit.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def admin_schedules(request):
    """Admin view for managing schedules and their prices."""
    # Handle schedule actions
    if request.method == 'POST':
        action = request.POST.get('action')
        schedule_id = request.POST.get('schedule_id')
        
        if action and schedule_id:
            try:
                schedule = Schedule.objects.get(id=schedule_id)
                if action == 'activate':
                    schedule.is_available = True
                    schedule.save()
                    messages.success(request, f'Schedule {schedule.bus.bus_number} - {schedule.route} has been activated.')
                elif action == 'deactivate':
                    schedule.is_available = False
                    schedule.save()
                    messages.success(request, f'Schedule {schedule.bus.bus_number} - {schedule.route} has been deactivated.')
                elif action == 'delete':
                    # Check if schedule has any bookings
                    if not Booking.objects.filter(schedule=schedule).exists():
                        schedule.delete()
                        messages.success(request, f'Schedule has been deleted.')
                    else:
                        messages.error(request, f'Cannot delete schedule - it has associated bookings.')
            except Schedule.DoesNotExist:
                messages.error(request, 'Schedule not found.')
    
    # Get search and filter parameters
    search_query = request.GET.get('search', '')
    bus_filter = request.GET.get('bus', '')
    route_filter = request.GET.get('route', '')
    status_filter = request.GET.get('status', '')
    
    # Build queryset with filters
    schedules = Schedule.objects.select_related('bus', 'route').all()
    
    if search_query:
        schedules = schedules.filter(
            Q(bus__bus_number__icontains=search_query) |
            Q(route__start_location__icontains=search_query) |
            Q(route__end_location__icontains=search_query)
        )
    
    if bus_filter:
        schedules = schedules.filter(bus__bus_number=bus_filter)
    
    if route_filter:
        schedules = schedules.filter(route__id=route_filter)
    
    if status_filter:
        if status_filter == 'available':
            schedules = schedules.filter(is_available=True)
        elif status_filter == 'unavailable':
            schedules = schedules.filter(is_available=False)
    
    # Order by departure time
    schedules = schedules.order_by('-departure_time')
    
    # Pagination
    paginator = Paginator(schedules, 10)  # Show 10 schedules per page
    page = request.GET.get('page')
    schedules = paginator.get_page(page)
    
    # Get schedule statistics
    total_schedules = Schedule.objects.count()
    available_schedules = Schedule.objects.filter(is_available=True).count()
    unavailable_schedules = Schedule.objects.filter(is_available=False).count()
    upcoming_schedules = Schedule.objects.filter(departure_time__gte=timezone.now()).count()
    
    # Get available buses and routes for filters
    buses = Bus.objects.filter(is_available=True).order_by('bus_number')
    routes = Route.objects.all().order_by('start_location')
    
    context = {
        'schedules': schedules,
        'total_schedules': total_schedules,
        'available_schedules': available_schedules,
        'unavailable_schedules': unavailable_schedules,
        'upcoming_schedules': upcoming_schedules,
        'buses': buses,
        'routes': routes,
        'search_query': search_query,
        'bus_filter': bus_filter,
        'route_filter': route_filter,
        'status_filter': status_filter,
    }
    
    return render(request, 'NelsaApp/admin_schedules.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def admin_support(request):
    """Enhanced admin support view with filtering and search."""
    from .models import Support
    
    # Handle clear all support messages
    if request.method == 'POST' and request.POST.get('action') == 'clear_all':
        try:
            # Get count before deletion for confirmation message
            deleted_count = Support.objects.count()
            
            # Delete all support messages
            Support.objects.all().delete()
            
            messages.success(request, f'Successfully cleared all {deleted_count} support messages.')
        except Exception as e:
            messages.error(request, f'Error clearing support messages: {str(e)}')
        return redirect('admin_support')
    
    # Handle form submission for responses
   # if request.method == 'POST' and request.POST.get('support_id'):
        #support_id = request.POST.get('support_id')
        #response = request.POST.get('admin_response')
        #priority = request.POST.get('priority')
        #status = request.POST.get('status')
        
        #try:
            #support = Support.objects.get(id=support_id)
            #support.admin_response = response
            #support.priority = priority
            #support.status = status
            #support.responded_by = request.user
            #support.response_date = timezone.now()
            #support.save()
            
            # Send email to user if response is provided
            #if response and support.email:
                #try:
                    # Create a clean, readable email template without any encryption
                    #email_subject = f"Re: {support.subject} - MOGHAMO EXPRESS Support"
                    #email_body = f"""
#Dear {support.name},

#Thank you for contacting MOGHAMO EXPRESS support.

#Your original message:
#Subject: {support.subject}
#Message: {support.message}

#Our Response:
#{response}

#If you have any further questions, please don't hesitate to contact us.

#Best regards,
#MOGHAMO EXPRESS Support Team
#support@moghamoexpress.com
#+237 682777850

#---
#This is a plain text email that can be read by any email client.
                    #"""
                    
            #send_mail(
                        #email_subject,
                        #email_body,
                        #'nelsadoh@gmail.com',
                        #[support.email],
                     
                       # fail_silently=False,
                    #)
                    #api_url = "https://api.publicapis.org/entries"
  #  try:
           # response = requests.get(api_url)
            # 200 means "OK" (everything worked as expected).
        #if response.status_code == 200:
       # print("\nRequest successful! Status Code: 200 (OK)")

        #  Access the response data (usually JSON)
        # .json() method converts the JSON response into a Python dictionary or list.
        #data = response.json()

        #else:
        # If the status code is not 200, something went wrong.
            #print(f"\nRequest failed! Status Code: {response.status_code}")
            #print(f"Response text: {response.text}") 

   # except requests.exceptions.RequestException as e:
    # This catches any network-related errors (e.g., no internet, DNS error)
       # print(f"\nAn error occurred during the request: {e}")
                    
                                         
        ##messages.success(request, f'Response sent to {support.email} and saved successfully.')
        #print('Testing email notification')
    #except Exception as e:
        #messages.warning(request, f'Response saved but email could not be sent: {str(e)}')
        #print(f'error while sending email {str(e)}')
                    
       # else:
        #messages.success(request, 'Response saved successfully.')
                
   # except Support.DoesNotExist:
        #messages.error(request, 'Support ticket not found.')
        
        #return redirect('admin_support')
    
    # Get search and filter parameters
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    priority_filter = request.GET.get('priority', '')
    
    # Build queryset with filters
    supports = Support.objects.all()
    
    if search_query:
        supports = supports.filter(
            Q(name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(subject__icontains=search_query) |
            Q(message__icontains=search_query)
        )
    
    if status_filter:
        supports = supports.filter(status=status_filter)
    
    if priority_filter:
        supports = supports.filter(priority=priority_filter)
    
    # Order by priority (urgent first) then by date
    supports = supports.order_by('-priority', '-created_at')
    
    # Pagination
    paginator = Paginator(supports, 10)  # Show 10 support tickets per page
    page = request.GET.get('page')
    supports = paginator.get_page(page)
    
    # Get statistics
    total_supports = Support.objects.count()
    open_supports = Support.objects.filter(status='OPEN').count()
    in_progress_supports = Support.objects.filter(status='IN_PROGRESS').count()
    resolved_supports = Support.objects.filter(status='RESOLVED').count()
    urgent_supports = Support.objects.filter(priority='URGENT').count()
    
    context = {
        'supports': supports,
        'total_supports': total_supports,
        'open_supports': open_supports,
        'in_progress_supports': in_progress_supports,
        'resolved_supports': resolved_supports,
        'urgent_supports': urgent_supports,
        'search_query': search_query,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'status_choices': Support.STATUS_CHOICES,
        'priority_choices': Support.PRIORITY_CHOICES,
    }
    
    return render(request, 'NelsaApp/admin_support.html', context)

# Custom error handlers
def bad_request_view(request, exception=None):
    """Custom 400 Bad Request handler."""
    return render(request, '400.html', status=400)

def page_not_found_view(request, exception=None):
    """Custom 404 Not Found handler."""
    return render(request, '404.html', status=404)

def server_error_view(request, exception=None):
    """Custom 500 Server Error handler."""
    return render(request, '500.html', status=500)

def send_email(request):
    subject = "Test Email from Django!"
    message = "This is a simple plain-text email sent from your Django application."
    from_email = settings.DEFAULT_FROM_EMAIL # Uses the email configured in settings.py
    recipient_list = ['richardafoudo07@gmail.com'] # Replace with a real email for testing
    
    try:
        send_mail(subject, message, from_email, recipient_list, fail_silently=False)
        status_message = "Email sent successfully!"
    except Exception as e:
        status_message = f"Failed to send email: {e}"

