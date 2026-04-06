from django import forms
from django.contrib.auth import authenticate
from .models import Login, Booking, Passenger
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

class LoginForm(AuthenticationForm):
    """
    Do not replace AuthenticationForm's username/password fields with plain CharField:
    the parent uses UsernameField and password with strip=False; replacing them breaks
    authentication for otherwise valid credentials.

    Optional: if the user types an email in the username box, resolve it to User.username
    so login works with email or username.
    """

    field_css = (
        'width: 100%; box-sizing: border-box; border: 1px solid #ccc; border-radius: 8px; '
        'height: 48px; padding: 0 16px; margin-top: 8px;'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Username or email'
        self.fields['username'].widget.attrs.update(
            {
                'class': 'login-field',
                'placeholder': 'Username or email',
                'autocomplete': 'username',
                'autocapitalize': 'none',
                'style': self.field_css,
            }
        )
        self.fields['password'].label = 'Password'
        self.fields['password'].widget.attrs.update(
            {
                'class': 'login-field',
                'placeholder': 'Password',
                'autocomplete': 'current-password',
                'style': self.field_css,
            }
        )

    def clean_username(self):
        value = (self.cleaned_data.get('username') or '').strip()
        if not value:
            return value
        if '@' in value:
            user = User.objects.filter(email__iexact=value).first()
            if user:
                return user.username
        return value

    def clean(self):
        """
        Extend AuthenticationForm.clean(): ModelBackend matches username case-sensitively,
        so the correct password fails if casing differs. Retry with case-insensitive
        username and with email lookup before showing the generic invalid-login error.
        """
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username is None or not password:
            return self.cleaned_data

        self.user_cache = authenticate(
            self.request, username=username, password=password
        )
        if self.user_cache is None:
            lookup = (username or '').strip()
            if lookup:
                u = User.objects.filter(username__iexact=lookup).first()
                if u is not None:
                    self.user_cache = authenticate(
                        self.request, username=u.username, password=password
                    )
                if self.user_cache is None:
                    u = User.objects.filter(email__iexact=lookup).first()
                    if u is not None:
                        self.user_cache = authenticate(
                            self.request, username=u.username, password=password
                        )
        if self.user_cache is None:
            raise self.get_invalid_login_error()
        self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data

class RegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        label='Email Address',
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Enter your email'
        })
    )
    phone_number = forms.CharField(
        required=True,
        max_length=15,
        label='Phone Number',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Enter your phone number (e.g., +1234567890)'
        })
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'phone_number', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Style all fields consistently
        self.fields['username'].widget.attrs.update({
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Choose a username'
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Enter password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Confirm password'
        })
    
    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            # Check if phone number already exists in Passenger model
            if Passenger.objects.filter(phone=phone_number).exists():
                raise forms.ValidationError("This phone number is already registered. Please use a different number.")
        return phone_number
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # Check if email already exists
            if User.objects.filter(email=email).exists():
                raise forms.ValidationError("This email address is already registered. Please use a different email.")
        return email
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            # Create or update Passenger profile
            phone_number = self.cleaned_data['phone_number']
            passenger, created = Passenger.objects.get_or_create(
                email=user.email,
                defaults={
                    'name': user.get_full_name() or user.username,
                    'phone': phone_number
                }
            )
            # Update if passenger already exists
            if not created:
                passenger.phone = phone_number
                passenger.name = user.get_full_name() or user.username
                passenger.save()
        return user

class BookingForm(forms.Form):
    class Meta:
        model = Booking
        fields = '__all__'

    app_name = 'booking'



