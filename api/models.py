from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone

# Validators
mobile_validator = RegexValidator(
    regex=r'^\d{10}$',
    message="Mobile number must be exactly 10 digits."
)

aadhar_validator = RegexValidator(
    regex=r'^\d{12}$',
    message="Aadhar number must be exactly 12 digits."
)

class Role(models.Model):
    """
    Role table for user types
    1 - Superadmin
    2 - Admin
    3 - Vendor
    4 - User
    """
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'tbl_role'
        managed = False


class UserInfo(models.Model):
    user_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    contact_number = models.CharField(
        max_length=15,
        unique=True,
        validators=[mobile_validator]
    )
    role_id = models.IntegerField()
    aadhar_number = models.CharField(
        max_length=225,
        unique=True,
        validators=[aadhar_validator],
        blank=True,
        null=True
    )
    # Store Azure URLs instead of ImageField
    aadhar_img = models.URLField(max_length=5000, blank=True, null=True)
    stamp_img = models.URLField(max_length=5000, blank=True, null=True)
    certificate = models.URLField(max_length=5000, blank=True, null=True)
    is_approved = models.CharField(
        max_length=20, 
        blank=True, 
        null=True,
        choices=[('pending', 'Pending'), ('approved', 'Approved'), ('declined', 'Declined')],
        help_text="Approval status for vendors: pending/approved/declined"
    )

    decline_reason = models.TextField(blank=True, null=True)  

    
    # Tracking fields
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=45, blank=True, null=True)  # Stores role_id or user identifier
    updated_by = models.CharField(max_length=45, blank=True, null=True)
    deleted_by = models.CharField(max_length=45, blank=True, null=True)
    active_status = models.CharField(
        max_length=45, 
        default='1',
        help_text="1 = logged in/active, 0 = logged out/inactive")
    user_lat = models.CharField(max_length=50, blank=True, null=True)  # or DecimalField
    user_long = models.CharField(max_length=50, blank=True, null=True)  # or DecimalField
    password = models.CharField(max_length=555, blank=True, null=True)  # for hashed password

    # Django auth compatibility attributes
    USERNAME_FIELD = 'contact_number'
    REQUIRED_FIELDS = ['name']

    @property
    def is_anonymous(self):
        return False

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return self.active_status == '1'

    def __str__(self):
        return f"{self.name} ({self.contact_number})"

    class Meta:
        db_table = "tbl_user"
        managed = False

    def save(self, *args, **kwargs):
        self.full_clean()  
        super().save(*args, **kwargs)