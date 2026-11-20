from rest_framework import serializers
from .models import UserInfo 

class UserInfoSerializer(serializers.ModelSerializer):
    # Accept URLs for images
    aadhar_img = serializers.URLField(required=False, allow_null=True, allow_blank=True)
    stamp_img = serializers.URLField(required=False, allow_null=True, allow_blank=True)
    aadhar_number = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    certificate = serializers.URLField(required=False, allow_null=True, allow_blank=True)  # NEW

    # New optional fields
    user_lat = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    user_long = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    password = serializers.CharField(required=False, allow_null=True, allow_blank=True, write_only=True)
    
    # Add is_approved field
    is_approved = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    decline_reason = serializers.CharField(required=False, allow_null=True, allow_blank=True)  # NEW

    # Tracking fields - read only for created_at
    created_at = serializers.DateTimeField(read_only=True)
    created_by = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    updated_by = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    deleted_by = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    active_status = serializers.CharField(required=False, default='1')

    class Meta:
        model = UserInfo
        fields = '__all__'
        extra_kwargs = {
            'password': {'write_only': True}  # Ensures password is not returned in responses
        }

    def validate_contact_number(self, value):
        """Ensure contact number is exactly 10 digits."""
        if not value.isdigit() or len(value) != 10:
            raise serializers.ValidationError("Mobile number must be exactly 10 digits.")
        return value

    def validate_aadhar_number(self, value):
        """Ensure Aadhar number is exactly 12 digits and unique if provided."""
        if value:
            if not value.isdigit() or len(value) != 12:
                raise serializers.ValidationError("Aadhar number must be exactly 12 digits.")
            
            # Check uniqueness
            user_id = self.instance.user_id if self.instance else None
            if UserInfo.objects.exclude(user_id=user_id).filter(aadhar_number=value).exists():
                raise serializers.ValidationError("Aadhar number already exists.")
        return value

    def validate_active_status(self, value):
        """Ensure active_status is either '0' or '1'."""
        if value not in ['0', '1']:
            raise serializers.ValidationError("Active status must be '0' (logged out) or '1' (logged in).")
        return value

    def validate_user_lat(self, value):
        """Validate latitude if provided."""
        if value:
            try:
                lat = float(value)
                if lat < -90 or lat > 90:
                    raise serializers.ValidationError("Latitude must be between -90 and 90.")
            except ValueError:
                raise serializers.ValidationError("Invalid latitude format.")
        return value

    def validate_user_long(self, value):
        """Validate longitude if provided."""
        if value:
            try:
                lon = float(value)
                if lon < -180 or lon > 180:
                    raise serializers.ValidationError("Longitude must be between -180 and 180.")
            except ValueError:
                raise serializers.ValidationError("Invalid longitude format.")
        return value

    def validate(self, attrs):
        # Ensure optional fields are set to None if missing
        optional_fields = ['aadhar_number', 'aadhar_img', 'stamp_img', 'deleted_by', 
                          'user_lat', 'user_long', 'password', 'is_approved']
        for field in optional_fields:
            if field not in attrs or not attrs.get(field):
                attrs[field] = None
        return attrs


