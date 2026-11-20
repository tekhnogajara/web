# from azure.storage.blob import BlobServiceClient, PublicAccess, generate_blob_sas, BlobSasPermissions
# from django.conf import settings
# from datetime import datetime, timedelta
# import os
# from azure.core.exceptions import ResourceNotFoundError

# class AzureStorageService:
#     def __init__(self):
#         self.connection_string = settings.AZURE_STORAGE_CONNECTION_STRING
#         self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
#         self.containers = settings.AZURE_CONTAINERS
#         # Extract account name and key from connection string
#         conn_parts = dict(item.split('=', 1) for item in self.connection_string.split(';') if '=' in item)
#         self.account_name = conn_parts.get('AccountName')
#         self.account_key = conn_parts.get('AccountKey')
    
#     def create_containers(self):
#         """Create containers if they don't exist"""
#         for container_name in self.containers.values():
#             try:
#                 # Create container without public access
#                 self.blob_service_client.create_container(container_name)
#                 print(f"Container '{container_name}' created successfully!")
#             except Exception as e:
#                 print(f"Container '{container_name}' already exists or error: {e}")
    
#     def upload_image(self, container_type, file_obj, original_filename=None):
#         """
#         Upload image to Azure Blob Storage
#         :param container_type: 'AADHAR' or 'STAMP'
#         :param file_obj: Django UploadedFile object
#         :param original_filename: Original filename (optional)
#         :return: SAS URL of uploaded image (valid for 10 years)
#         """
#         container_name = self.containers.get(container_type)
#         if not container_name:
#             raise ValueError(f"Invalid container type: {container_type}")
        
#         # Generate unique filename
#         timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
#         ext = os.path.splitext(original_filename or file_obj.name)[1]
#         filename = f"{container_type.lower()}_{timestamp}{ext}"
        
#         # Upload to Azure
#         blob_client = self.blob_service_client.get_blob_client(
#             container=container_name, 
#             blob=filename
#         )
        
#         # Reset file pointer to beginning
#         file_obj.seek(0)
#         blob_client.upload_blob(file_obj, overwrite=True)
        
#         # Generate SAS token (valid for 10 years)
#         sas_token = generate_blob_sas(
#             account_name=self.account_name,
#             container_name=container_name,
#             blob_name=filename,
#             account_key=self.account_key,
#             permission=BlobSasPermissions(read=True),
#             expiry=datetime.utcnow() + timedelta(days=3650)  
#         )
        
#         # Return URL with SAS token
#         return f"{blob_client.url}?{sas_token}"
    
    
    

#     def delete_image(self, container_type, blob_name):
#         container_name = self.containers.get(container_type)

#         blob_client = self.blob_service_client.get_blob_client(
#             container=container_name,
#             blob=blob_name
#         )

#         try:
#             blob_client.delete_blob()
#         except ResourceNotFoundError:
#             print(f"Blob not found: {blob_name}")

    
    



from azure.storage.blob import BlobServiceClient, PublicAccess, generate_blob_sas, BlobSasPermissions
from django.conf import settings
from datetime import datetime, timedelta
import os
from azure.core.exceptions import ResourceNotFoundError

class AzureStorageService:
    def __init__(self):
        self.connection_string = settings.AZURE_STORAGE_CONNECTION_STRING
        self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
        self.containers = settings.AZURE_CONTAINERS
        # Extract account name and key from connection string
        conn_parts = dict(item.split('=', 1) for item in self.connection_string.split(';') if '=' in item)
        self.account_name = conn_parts.get('AccountName')
        self.account_key = conn_parts.get('AccountKey')
    
    def create_containers(self):
        """Create containers if they don't exist"""
        for container_name in self.containers.values():
            try:
                # Create container without public access
                self.blob_service_client.create_container(container_name)
                print(f"Container '{container_name}' created successfully!")
            except Exception as e:
                print(f"Container '{container_name}' already exists or error: {e}")
    
    def upload_image(self, container_type, file_obj, original_filename=None):
        """
        Upload image to Azure Blob Storage
        :param container_type: 'AADHAR', 'STAMP', or 'CERTIFICATE'
        :param file_obj: Django UploadedFile object
        :param original_filename: Original filename (optional)
        :return: SAS URL of uploaded image (valid for 10 years)
        """
        container_name = self.containers.get(container_type)
        if not container_name:
            raise ValueError(f"Invalid container type: {container_type}. Valid types: AADHAR, STAMP, CERTIFICATE")
        
        # Generate unique filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        ext = os.path.splitext(original_filename or file_obj.name)[1]
        filename = f"{container_type.lower()}_{timestamp}{ext}"
        
        # Upload to Azure
        blob_client = self.blob_service_client.get_blob_client(
            container=container_name, 
            blob=filename
        )
        
        # Reset file pointer to beginning
        file_obj.seek(0)
        blob_client.upload_blob(file_obj, overwrite=True)
        
        # Generate SAS token (valid for 10 years)
        sas_token = generate_blob_sas(
            account_name=self.account_name,
            container_name=container_name,
            blob_name=filename,
            account_key=self.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(days=3650)  
        )
        
        # Return URL with SAS token
        return f"{blob_client.url}?{sas_token}"
    
    def delete_image(self, container_type, blob_name):
        """
        Delete image from Azure Blob Storage
        :param container_type: 'AADHAR', 'STAMP', or 'CERTIFICATE'
        :param blob_name: Name of the blob to delete
        """
        container_name = self.containers.get(container_type)
        if not container_name:
            raise ValueError(f"Invalid container type: {container_type}")
        
        blob_client = self.blob_service_client.get_blob_client(
            container=container_name,
            blob=blob_name
        )

        try:
            blob_client.delete_blob()
            print(f"Blob deleted successfully: {blob_name}")
        except ResourceNotFoundError:
            print(f"Blob not found: {blob_name}")
        except Exception as e:
            print(f"Error deleting blob: {e}")
            raise