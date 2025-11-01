# Create your models here.
from django.db import models
from django.contrib.auth.models import User

class Bus(models.Model):
    BUS_TYPES = [('Luxury', 'Luxury'), ('Standard', 'Standard'), ('Express', 'Express')]
    bus_number = models.CharField(max_length=20, unique=True)
    bus_type = models.CharField(max_length=10, choices=BUS_TYPES)
    capacity = models.IntegerField()
    is_available = models.BooleanField(default=True)
    operator = models.CharField(max_length=100, blank=True, null=True)

    def str(self):
        return self.bus_number

    def _str_(self):
        return f"{self.bus.name} - Seat {self.seat_number}"

class Route(models.Model):
    start_location = models.CharField(max_length=100)
    end_location = models.CharField(max_length=100)
    distance = models.FloatField()
    duration = models.FloatField(default=0)  # Duration in hours
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # Base price for the route

    def __str__(self):
        return f"{self.start_location} → {self.end_location}"
    
    def save(self, *args, **kwargs):
        # Check if this is an update and price has changed
        if self.pk:
            try:
                old_route = Route.objects.get(pk=self.pk)
                if old_route.price != self.price:
                    # Update all schedules that use the route's base price
                    Schedule.objects.filter(route=self).update(price=self.price)
            except Route.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)

    class Meta:
        unique_together = ('start_location', 'end_location')

class Passenger(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, unique=True)

    def _str_(self):
        return self.name

class Schedule(models.Model):
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE)
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='schedules')
    departure_time = models.DateTimeField()
    arrival_time = models.DateTimeField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.bus.bus_number} - {self.route}"
    
    def save(self, *args, **kwargs):
        # If this is a new schedule and no price is set, use the route's price
        if not self.pk and not self.price:
            self.price = self.route.price
        super().save(*args, **kwargs)

class BookingGroup(models.Model):
    """Model to group multiple seat bookings together for payment."""
    passenger = models.ForeignKey(Passenger, on_delete=models.CASCADE)
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=[('Pending', 'Pending'), ('Confirmed', 'Confirmed'), ('Cancelled', 'Cancelled')], default='Pending')
    transaction_id = models.CharField(max_length=100, blank=True, null=True, help_text="Transaction ID for payment verification")
    transaction_verified = models.BooleanField(default=False, help_text="Whether the transaction has been verified by admin")
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_bookings')
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Booking Group {self.id} - {self.passenger.name} ({self.bookings.count()} seats)"
    
    def get_total_seats(self):
        return self.bookings.count()
    
    def get_seat_numbers(self):
        return [booking.seat_number for booking in self.bookings.all()]

class Booking(models.Model):
    STATUS_CHOICES = [('Confirmed', 'Confirmed'), ('Cancelled', 'Cancelled'), ('Pending', 'Pending')]
    passenger = models.ForeignKey(Passenger, on_delete=models.CASCADE)
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE)
    seat_number = models.IntegerField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')
    booking_date = models.DateTimeField(auto_now_add=True)
    booking_group = models.ForeignKey(BookingGroup, on_delete=models.CASCADE, related_name='bookings', null=True, blank=True)

    def _str_(self):
        return f"Booking {self.id} - {self.passenger.name}"
    
    


    
class Login(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    
    def _str_(self):
        return self.booking

class Seat(models.Model):
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE, related_name='seats', null=True, blank=True)
    row = models.IntegerField(default=1)
    column = models.IntegerField()
    is_booked = models.BooleanField(default=False)

    def __str__(self):
        return f"Bus {self.bus.bus_number if self.bus else 'Unknown'} - Seat {self.row}-{self.column} ({'Booked' if self.is_booked else 'Available'})"

    class Meta:
        unique_together = ('bus', 'row', 'column')

class Payment(models.Model):
    PAYMENT_METHODS = [
        ('MOMO', 'MTN Mobile Money'),
        ('ORANGE', 'Orange Money'),
        ('CARD', 'Credit/Debit Card'),
    ]
    
    PAYMENT_STATUS = [
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('REFUNDED', 'Refunded'),
    ]
    
    booking_group = models.OneToOneField(BookingGroup, on_delete=models.CASCADE, related_name='payment', null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHODS)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    payment_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=PAYMENT_STATUS, default='PENDING')
    payment_details = models.JSONField(default=dict, blank=True)  # Store payment-specific details
    
    def __str__(self):
        return f"Payment for Booking Group #{self.booking_group.id} - {self.payment_method} - {self.status}"
    
    class Meta:
        ordering = ['-payment_date']

class Support(models.Model):
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
        ('CLOSED', 'Closed'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]
    
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=15, blank=True, null=True)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    admin_response = models.TextField(blank=True, null=True)
    responded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='support_responses')
    response_date = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Support #{self.id} - {self.subject} ({self.status})"
    
    class Meta:
        ordering = ['-created_at']

class Review(models.Model):
    RATING_CHOICES = [
        (1, '1 Star - Poor'),
        (2, '2 Stars - Fair'),
        (3, '3 Stars - Good'),
        (4, '4 Stars - Very Good'),
        (5, '5 Stars - Excellent'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='reviews', null=True, blank=True)
    rating = models.IntegerField(choices=RATING_CHOICES)
    title = models.CharField(max_length=200)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_approved = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Review by {self.user.username} - {self.rating} stars"
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['user', 'booking']  # One review per booking per user
