# vendor_services.py
import math
from django.db import connection
from datetime import datetime
import logging


# class VendorService:
#     @staticmethod
#     def calculate_distance(lat1, lon1, lat2, lon2):
#         """
#         Calculate distance between two points using Haversine formula
#         Returns distance in kilometers
#         """
#         R = 6371  # Earth's radius in kilometers
        
#         try:
#             lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
            
#             dlat = math.radians(lat2 - lat1)
#             dlon = math.radians(lon2 - lon1)
            
#             a = (math.sin(dlat/2) * math.sin(dlat/2) + 
#                  math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
#                  math.sin(dlon/2) * math.sin(dlon/2))
            
#             c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
#             distance = R * c
            
#             return round(distance, 2)  # Round to 2 decimal places
            
#         except (ValueError, TypeError):
#             return None


# vendor_services.py
import logging
from django.db import connection

logger = logging.getLogger(__name__)

class VendorService:
    @staticmethod
    def calculate_distance(lat1, lon1, lat2, lon2):
        """Haversine formula to calculate km distance (fallback)"""
        from math import radians, cos, sin, asin, sqrt
        if None in (lat1, lon1, lat2, lon2):
            return None
        lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
        R = 6371
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        return R * c

    @staticmethod
    def send_notification_to_vendors(order_id, user_id, order_lat, order_lon, order_at):
        """
        Find all approved, active vendors within 4km and create notifications.
        Uses a stable SQL formula that avoids ACOS domain errors.
        """
        try:
            with connection.cursor() as cursor:
                # Stable distance formula using ASIN (no ACOS domain issues)
                cursor.execute("""
                    SELECT 
                        user_id,
                        name,
                        contact_number,
                        user_lat,
                        user_long,
                        aadhar_number,
                        aadhar_img,
                        stamp_img,
                        ROUND(6371 * 2 * ASIN(SQRT(
                            POWER(SIN(RADIANS(%s - user_lat) / 2), 2) +
                            COS(RADIANS(%s)) * COS(RADIANS(user_lat)) *
                            POWER(SIN(RADIANS(%s - user_long) / 2), 2)
                        )), 2) AS distance_km
                    FROM tbl_user
                    WHERE role_id = 3
                      AND active_status = '1'
                      AND is_approved = 'approved'
                      AND user_lat IS NOT NULL
                      AND user_long IS NOT NULL
                    HAVING distance_km <= 4
                    ORDER BY distance_km
                """, [order_lat, order_lat, order_lon])

                vendors = cursor.fetchall()
                nearby = []
                for v in vendors:
                    nearby.append({
                        "vendor_id": v[0],
                        "name": v[1],
                        "contact_number": v[2],
                        "latitude": float(v[3]),
                        "longitude": float(v[4]),
                        "distance_km": float(v[8]) if v[8] is not None else None,
                        "aadhar_number": v[5],
                        "aadhar_img": v[6],
                        "stamp_img": v[7]
                    })

                # Insert notifications
                notified_count = 0
                for vendor in nearby:
                    try:
                        cursor.execute("""
                            INSERT INTO tbl_notification_details
                            (order_id, user_id, order_at)
                            VALUES (%s, %s, %s)
                        """, [order_id, vendor["vendor_id"], order_at])
                        notified_count += 1
                    except Exception as e:
                        logger.error(f"Failed to insert notification for vendor {vendor['vendor_id']}: {e}")

                return {
                    "total_vendors_notified": notified_count,
                    "nearby_vendors": nearby
                }

        except Exception as e:
            logger.exception("Error in send_notification_to_vendors")
            raise  # Re-raise so the view catches it


    @staticmethod
    def get_nearby_vendors(order_lat, order_lon, radius_km=4):
        """
        Get all approved vendors within specified radius
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    user_id, 
                    name, 
                    contact_number, 
                    user_lat, 
                    user_long,
                    aadhar_number,
                    aadhar_img,
                    stamp_img
                FROM gajara.tbl_user 
                WHERE role_id = 3 
                    AND is_approved = 'approved'
                    AND active_status = '1'
                    AND user_lat IS NOT NULL 
                    AND user_long IS NOT NULL
            """)
            
            vendors = cursor.fetchall()
            nearby_vendors = []
            
            for vendor in vendors:
                vendor_id, name, contact, lat, lon, aadhar, aadhar_img, stamp_img = vendor
                
                distance = VendorService.calculate_distance(
                    order_lat, order_lon, lat, lon
                )
                
                if distance is not None and distance <= radius_km:
                    nearby_vendors.append({
                        'vendor_id': vendor_id,
                        'name': name,
                        'contact_number': contact,
                        'latitude': float(lat) if lat else None,
                        'longitude': float(lon) if lon else None,
                        'distance_km': distance,
                        'aadhar_number': aadhar,
                        'aadhar_img': aadhar_img,
                        'stamp_img': stamp_img
                    })
            
            # Sort by distance
            nearby_vendors.sort(key=lambda x: x['distance_km'])
            
            return nearby_vendors

    # @staticmethod
    # def send_notification_to_vendors(order_id, user_id, order_lat, order_lon, order_at):
    #     """
    #     Send order notification to nearby vendors and record in tbl_notification_details
    #     """
    #     nearby_vendors = VendorService.get_nearby_vendors(order_lat, order_lon)
        
    #     with connection.cursor() as cursor:
    #         for vendor in nearby_vendors:
    #             cursor.execute("""
    #                 INSERT INTO gajara.tbl_notification_details 
    #                 (order_id, user_id, order_at) 
    #                 VALUES (%s, %s, %s)
    #             """, [order_id, vendor['vendor_id'], order_at])
        
    #     return {
    #         'total_vendors_notified': len(nearby_vendors),
    #         'nearby_vendors': nearby_vendors
    #     }

    @staticmethod
    def get_vendor_orders(vendor_id, status_filter=None):
        """
        Get all orders notified to a specific vendor
        status_filter: 'pending' - only orders not accepted/rejected
                    'accepted' - only accepted orders
                    'rejected' - only rejected orders
                    None - all orders
        """
        with connection.cursor() as cursor:
            query = """
                SELECT 
                    nd.n_id,
                    nd.order_id,
                    nd.user_id,
                    nd.accepted_by,
                    nd.rejected_by,
                    nd.accepted_at,
                    nd.rejected_at,
                    nd.reject_reason,
                    nd.order_at,
                    sd.total_amount,
                    sd.payment_mode,
                    sd.order_status,
                    sd.customer_order_status,
                    sd.user_lat as customer_lat,
                    sd.user_long as customer_long,
                    sd.random_otp,
                    sd.confirm_at,
                    sd.cancel_at,
                    u.name as customer_name,
                    u.contact_number as customer_mobile,
                    u.user_lat as vendor_lat,
                    u.user_long as vendor_long
                FROM gajara.tbl_notification_details nd
                INNER JOIN gajara.tbl_sales_details sd ON nd.order_id = sd.order_id
                INNER JOIN gajara.tbl_user u ON nd.user_id = u.user_id
                WHERE nd.user_id = %s
            """
            params = [vendor_id]
            
            if status_filter == 'pending':
                # Orders that are PENDING and this vendor hasn't acted on them
                query += """ AND sd.order_status = 'PENDING' 
                            AND nd.accepted_by IS NULL 
                            AND nd.rejected_by IS NULL"""
            elif status_filter == 'accepted':
                # Orders that this vendor has accepted (even if they later rejected)
                query += " AND nd.accepted_by IS NOT NULL"
            elif status_filter == 'rejected':
                # Orders that this vendor has rejected
                query += " AND nd.rejected_by IS NOT NULL"
            
            query += " ORDER BY nd.order_at DESC"
            
            cursor.execute(query, params)
            notifications = cursor.fetchall()
            
            result = []
            for n in notifications:
                # Calculate distance
                vendor_lat = n[20]
                vendor_lon = n[21]
                customer_lat = n[13]
                customer_lon = n[14]
                
                distance = VendorService.calculate_distance(
                    vendor_lat, vendor_lon, customer_lat, customer_lon
                ) if vendor_lat and vendor_lon and customer_lat and customer_lon else None
                
                # Determine if this vendor accepted and then rejected
                vendor_action = 'none'
                if n[3] == vendor_id and n[11] == 'PENDING':
                    vendor_action = 'accepted_then_rejected'
                elif n[3] == vendor_id:
                    vendor_action = 'accepted'
                elif n[4] == vendor_id:
                    vendor_action = 'rejected'
                
                # Get current accepting vendor info if any
                accepting_vendor_name = None
                if n[3] and n[3] != vendor_id:
                    with connection.cursor() as inner_cursor:
                        inner_cursor.execute("SELECT name FROM gajara.tbl_user WHERE user_id = %s", [n[3]])
                        accepting_vendor = inner_cursor.fetchone()
                        accepting_vendor_name = accepting_vendor[0] if accepting_vendor else "Another vendor"
                
                result.append({
                    'notification_id': n[0],
                    'order_id': n[1],
                    'vendor_id': n[2],
                    'accepted_by': n[3],
                    'rejected_by': n[4],
                    'accepted_at': str(n[5]) if n[5] else None,
                    'rejected_at': str(n[6]) if n[6] else None,
                    'reject_reason': n[7],
                    'order_at': str(n[8]),
                    'vendor_action': vendor_action,
                    'order_details': {
                        'total_amount': float(n[9]) if n[9] else 0,
                        'payment_mode': n[10],
                        'order_status': n[11],
                        'customer_order_status': n[12],
                        'customer_latitude': float(n[13]) if n[13] else None,
                        'customer_longitude': float(n[14]) if n[14] else None,
                        'otp': n[15],
                        'confirm_at': str(n[16]) if n[16] else None,
                        'cancel_at': str(n[17]) if n[17] else None,
                        'customer_name': n[18],
                        'customer_mobile': n[19],
                        'distance_from_vendor_km': distance,
                        'accepted_by_other': n[3] and n[3] != vendor_id,
                        'accepted_by_name': accepting_vendor_name
                    }
                })
            
            return result