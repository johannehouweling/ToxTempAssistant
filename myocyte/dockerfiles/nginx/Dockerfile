FROM nginx:stable-alpine

RUN rm /etc/nginx/conf.d/default.conf

COPY nginx.conf /etc/nginx/conf.d

# Copy error pages (404, 500)
# COPY error_pages /usr/share/nginx/html/error_pages
# RUN chmod 644 /usr/share/nginx/html/error_pages