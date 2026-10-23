FROM node:20-alpine AS build

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:1.27-alpine

# Only substitute our backend address; preserve Nginx variables like $host and $uri.
ENV NGINX_ENVSUBST_FILTER=^BACKEND_HOSTPORT$
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
