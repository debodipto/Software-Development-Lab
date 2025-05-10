from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import logout, authenticate, login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User

from .cart import Cart
from .forms import *
from django.contrib.auth.forms import UserCreationForm
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash

from .models import *
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.core.cache import cache


@login_required(login_url='/login/')
def logout_view(request):
    logout(request)
    return render(request, 'logout.html')


def about_view(request):
    return render(request, 'about_us.html')


def contact_view(request):
    return render(request, 'contact_us.html')


def index(request):
    # Add caching for approved bikes
    bikes = cache.get('index_bikes')
    if bikes is None:
        bikes = BikeBuyAndSell.objects.select_related('category', 'user').filter(
            status="Approved"
        ).order_by('-id')[:12]  # Limit to 12 recent bikes
        cache.set('index_bikes', bikes, 300)

    # Add caching for banners
    banners = cache.get('index_banners') 
    if banners is None:
        banners = Banner.objects.all().order_by('-id')
        cache.set('index_banners', banners, 600)

    context = {
        'bike_buy_and_sell': bikes,
        'banners': banners,
        'categories': Category.objects.all(),
    }
    return render(request, 'index.html', context)


def user_login(request):
    if request.user.is_authenticated:
        return redirect('bike_buy_and_sell:bike_index')  # changed redirect target

    form = LoginForm()
    context = {'form': form}
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                messages.success(request, 'Logged in successfully')
                return redirect('bike_buy_and_sell:bike_index')  # changed redirect target
            else:
                messages.error(request, 'Login failed. Please check your username and password.')
    return render(request, 'login.html', context)


class SignUpView(CreateView):
    form_class = CustomUserCreationForm
    success_url = reverse_lazy("bike_buy_and_sell:login")  # Updated URL
    template_name = "registration.html"

    def form_valid(self, form):
        user = form.save()  # Save the user and activate immediately
        messages.success(self.request, "Registration successful! You can now log in.")
        return redirect(self.success_url)


@login_required(login_url='/login/')
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important to maintain user's session
            messages.success(request, 'Your password was successfully updated!')
            return redirect('bike_buy_and_sell:profile')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'change_password.html', {'form': form})


@login_required(login_url='/login')
def profile(request):
    user = request.user
    profile = getattr(user, 'profile', None)  # Get the profile if it exists
    context = {
        'user': user,
        'profile': profile,
    }
    return render(request, 'profile.html', context)


@login_required(login_url='/login')
def update_profile(request):
    user = request.user
    profile = getattr(user, 'profile', None)

    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES)
        if form.is_valid():
            # Update user fields
            user.first_name = form.cleaned_data.get('first_name')
            user.last_name = form.cleaned_data.get('last_name')
            user.email = form.cleaned_data.get('email')
            user.save()

            # Update or create the profile
            if profile:
                profile.profile_picture = form.cleaned_data.get('profile_picture') or profile.profile_picture
                profile.save()
            else:
                Profile.objects.create(user=user, profile_picture=form.cleaned_data.get('profile_picture'))

            messages.success(request, "Profile updated successfully!")
            return redirect('bike_buy_and_sell:profile')  # updated redirect with namespace
    else:
        form = ProfileUpdateForm(initial={
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
        })

    context = {
        'form': form,
        'profile': profile,
    }
    return render(request, 'update_profile.html', context)


@login_required(login_url='/login')
def booking_list(request):
    booking_list = Orders.objects.filter(user=request.user).order_by('-id')
    context = {
        "booking_list": booking_list
    }
    return render(request, 'booking_list.html', context)


def buy_list(request):
    # Add caching
    cache_key = f'buy_list_{request.GET.get("category", "")}_{request.GET.get("min_price", "")}_{request.GET.get("max_price", "")}'
    queryset = cache.get(cache_key)
    
    if queryset is None:
        queryset = BikeBuyAndSell.objects.select_related('category', 'user').filter(status='Approved').order_by('-id')
        
        # Filtering logic
        category_id = request.GET.get('category')
        min_price = request.GET.get('min_price')
        max_price = request.GET.get('max_price')
        
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)
            
        cache.set(cache_key, queryset, 300)  # Cache for 5 minutes

    # Add pagination
    paginator = Paginator(queryset, 12)  # Show 12 bikes per page
    page = request.GET.get('page')
    bikes = paginator.get_page(page)

    context = {
        'bike_buy_and_sell': bikes,
        'categories': Category.objects.all(),  # Pass categories for the dropdown
    }
    return render(request, 'buy_list.html', context)


@login_required(login_url='/login')
def sell_views(request):
    category = Category.objects.all()
    context = {
        'category': category
    }
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            price = request.POST.get('price')
            description = request.POST.get('description')
            category_id = request.POST.get('category')
            image_list = request.FILES.getlist('image')

            # Validate required fields
            if not (name and price and description and category_id):
                messages.error(request, "All fields are required.")
                return render(request, 'sell.html', context)

            # Validate category
            try:
                category_obj = Category.objects.get(pk=category_id)
            except Category.DoesNotExist:
                messages.error(request, "Invalid category selected.")
                return render(request, 'sell.html', context)

            # Create the bike listing
            bike_buy_and_sell_create = BikeBuyAndSell.objects.create(
                name=name,
                price=price,
                description=description,
                category=category_obj,
                user=request.user
            )

            # Handle uploaded images
            if not image_list:
                messages.error(request, "At least one image is required.")
                bike_buy_and_sell_create.delete()
                return render(request, 'sell.html', context)

            for image in image_list:
                BikeBuyAndSellImage.objects.create(
                    bike_buy_and_sell=bike_buy_and_sell_create,
                    image=image
                )

            # Updated success message after bike is added
            messages.success(request, "Your bike has been added.")
            return redirect('bike_buy_and_sell:sell_list')
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            return render(request, 'sell.html', context)
    return render(request, 'sell.html', context)


@login_required(login_url='/login')
def sell_list(request):
    bikes = BikeBuyAndSell.objects.filter(user=request.user)

    # Handle form submission for adding a new bike
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            price = request.POST.get('price')
            description = request.POST.get('description')
            category_id = request.POST.get('category')
            image_list = request.FILES.getlist('image')

            # Validate required fields
            if not (name and price and description and category_id):
                messages.error(request, "All fields are required.")
            else:
                category_obj = Category.objects.get(pk=category_id)
                bike = BikeBuyAndSell.objects.create(
                    name=name,
                    price=price,
                    description=description,
                    category=category_obj,
                    user=request.user
                )
                for image in image_list:
                    BikeBuyAndSellImage.objects.create(bike_buy_and_sell=bike, image=image)
                messages.success(request, f"Bike added successfully! Status: {bike.status}")
                return redirect('bike_buy_and_sell:sell_list')  # updated redirect with namespace
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")

    # Search and filter functionality
    search_query = request.GET.get('search', '')
    selected_categories = request.GET.getlist('category', [])
    if search_query:
        bikes = bikes.filter(name__icontains=search_query)
    if selected_categories:
        bikes = bikes.filter(category_id__in=selected_categories)

    categories = Category.objects.all()
    context = {
        'bike_buy_and_sell': bikes,
        'categories': categories,
        'selected_categories': selected_categories,
    }
    return render(request, 'sell_list.html', context)


# any one can add product to cart, no need of signin
def add_to_cart_view(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(BikeBuyAndSell, id=product_id)
    form = CartAddProductForm(request.POST)
    if form.is_valid():
        cd = form.cleaned_data
        cart.add(product=product, quantity=1, update_quantity=cd.get('update', False))  # Default quantity to 1
    return redirect('bike_buy_and_sell:cart_detail')


def cart_detail(request):
    cart = Cart(request)
    for item in cart:
        item['update_quantity_form'] = CartAddProductForm(initial={'quantity': item['quantity'], 'update': True})
    return render(request, 'cart_detail.html', {'cart': cart})


def cart_update(request, product_id):
    if request.method == "POST":
        cart = Cart(request)
        product = get_object_or_404(BikeBuyAndSell, id=product_id)
        form = CartAddProductForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            cart.update(product=product, quantity=1, update_quantity=cd.get('update', False))  # Default quantity to 1
        return redirect('bike_buy_and_sell:cart_detail')


def cart_remove(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(BikeBuyAndSell, id=product_id)
    cart.remove(product)
    return redirect('bike_buy_and_sell:cart_detail')


@login_required(login_url='/login')
def order_create(request):
    cart = Cart(request)
    if request.method == 'POST':
        form = OrderCreateForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            user = User.objects.get(username=request.user)
            order = Orders.objects.create(
                user=user,
                email=cd['email'],
                mobile=cd['mobile'],
                address=cd['address'],
                total_price=cart.get_total_price()
            )
            for item in cart:
                OrderItem.objects.create(
                    order=order,
                    bike_buy_and_sell=item['product'],
                    price=item['price'],
                    quantity=item['quantity']
                )
            cart.clear()
            return render(request, 'order_created.html', {'order': order})
    else:
        form = OrderCreateForm()
    return render(request, 'checkout_create.html', {'form': form})


def search_view(request):
    # whatever user write in search box we get in query
    query = request.GET['query']
    products = BikeBuyAndSell.objects.all().filter(name__icontains=query)
    # word variable will be shown in html when user click on search button
    word = "Searched Result : {}".format(query)
    context = {
        'bike_buy_and_sell': products,
        'word': word,
    }
    return render(request, 'index.html', context)


def order_details(request, order_id):
    order = get_object_or_404(Orders, user=request.user, id=order_id)  # Use get_object_or_404 for safety
    products = OrderItem.objects.filter(order__id=order_id)
    return render(request, 'order_details.html', {'order': order, "products": products})


def product_detail(request, id):
    product = get_object_or_404(BikeBuyAndSell, id=id)
    seller = product.user  # Get the seller's user object
    cart_product_form = CartAddProductForm()
    context = {
        'product': product,
        'seller': seller,  # Pass the seller's information to the template
        'cart_product_form': cart_product_form,
    }
    return render(request, 'detail.html', context)


def category_based_bike(request, category_id):
    bike_buy_and_sell = BikeBuyAndSell.objects.filter(category__id=category_id)
    context = {
        'bike_buy_and_sell': bike_buy_and_sell,
    }
    return render(request, 'category_based_bike.html', context)


@login_required
def chat_support(request):
    if request.method == 'POST':
        message = request.POST.get('message')
        if message:
            ChatMessage.objects.create(
                user=request.user,
                message=message,
                is_admin=request.user.is_staff
            )
    # Fetch all messages for the current user
    messages_list = ChatMessage.objects.filter(user=request.user).order_by('timestamp')
    # Pass messages as "chat_messages" instead of "messages"
    return render(request, 'chat_support.html', {'chat_messages': messages_list})


def chat_support_redirect(request):
    if not request.user.is_authenticated:
        return redirect('login')
    return redirect('bike_buy_and_sell:chat_support')  # Use namespaced URL


@login_required
def user_chat_support(request):
    if request.method == 'POST':
        message = request.POST.get('message')
        if message:
            ChatMessage.objects.create(
                user=request.user,
                message=message,
                is_admin=False
            )
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success'})
            return redirect('bike_buy_and_sell:chat_support')  # updated redirect with namespace
    # Pass messages as "chat_messages" instead of "messages"
    messages_list = ChatMessage.objects.filter(user=request.user).order_by('timestamp')
    return render(request, 'chat_support.html', {'chat_messages': messages_list})


@login_required(login_url='/login/')
def edit_bike(request, bike_id):
    bike = get_object_or_404(BikeBuyAndSell, id=bike_id, user=request.user)
    if request.method == 'POST':
        bike.name = request.POST.get('name')
        bike.price = request.POST.get('price')
        bike.description = request.POST.get('description')
        bike.category_id = request.POST.get('category')
        bike.save()

        # Handle new image uploads
        images = request.FILES.getlist('images')
        for image in images:
            BikeBuyAndSellImage.objects.create(bike_buy_and_sell=bike, image=image)

        messages.success(request, "Bike listing updated successfully!")
        return redirect('bike_buy_and_sell:sell_list')  # updated redirect with namespace
    categories = Category.objects.all()
    return render(request, 'edit_bike.html', {'bike': bike, 'categories': categories})


@login_required(login_url='/login/')
def delete_bike(request, bike_id):
    bike = get_object_or_404(BikeBuyAndSell, id=bike_id, user=request.user)
    bike.delete()
    from django.core.cache import cache  # ensure cache is imported
    cache.clear()  # Clear cache to update buy list
    messages.success(request, "Bike listing deleted successfully!")
    return redirect('bike_buy_and_sell:sell_list')


@login_required(login_url='/login/')
def delete_bike_image(request, image_id):
    image = get_object_or_404(BikeBuyAndSellImage, id=image_id)
    if image.bike_buy_and_sell.user != request.user:
        return HttpResponseForbidden("You are not allowed to delete this image.")
    image.delete()
    messages.success(request, "Image deleted successfully!")
    return redirect('bike_buy_and_sell:edit_bike', bike_id=image.bike_buy_and_sell.id)  # updated redirect with namespace


@login_required
def admin_chat_support(request):
    if not request.user.is_staff:
        return redirect('bike_buy_and_sell:bike_index')  # Restrict access to admins only

    if request.method == 'POST':
        message = request.POST.get('message')
        user_id = request.POST.get('user_id')
        parent_id = request.POST.get('parent_id')  # Optional parent message id

        if parent_id:
            parent_msg = ChatMessage.objects.filter(id=parent_id).first()
            user = parent_msg.user if parent_msg else User.objects.get(id=user_id)
        else:
            parent_msg = None
            user = User.objects.get(id=user_id)

        if message:
            ChatMessage.objects.create(
                user=user,
                message=message,
                is_admin=True,
                parent=parent_msg
            )
            if parent_msg:
                parent_msg.status = 'resolved'
                parent_msg.save()
    # Fetch all users with messages
    users_with_messages = User.objects.filter(chat_messages__isnull=False).distinct()
    selected_user_id = request.GET.get('user_id', users_with_messages.first().id if users_with_messages else None)
    selected_user = User.objects.get(id=selected_user_id) if selected_user_id else None
    # Order messages to group thread conversations
    messages_list = ChatMessage.objects.filter(user=selected_user).order_by('timestamp') if selected_user else []
    return render(request, 'bike_buy_and_sell:admin_chat_support.html', {
        'users': users_with_messages,
        'selected_user': selected_user,
        'messages': messages_list
    })


def activate_account(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, "Your account has been activated successfully!")
        return redirect('bike_buy_and_sell:bike_indexlogin')
    else:
        messages.error(request, "The activation link is invalid or has expired.")
        return render(request, 'activation_invalid.html')


@staff_member_required
def admin_order_details(request, order_id):
    order = get_object_or_404(Orders, id=order_id)
    items = OrderItem.objects.filter(order=order)
    return render(request, 'admin/order_details.html', {'order': order, 'items': items})


@login_required
def chat_support_popup(request):
    messages_list = ChatMessage.objects.filter(user=request.user).order_by('timestamp')
    return render(request, 'partials/chat_popup.html', {'chat_messages': messages_list})

