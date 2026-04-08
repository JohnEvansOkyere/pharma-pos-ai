🔹 Step 1: Create the user
CREATE USER pharma_user WITH PASSWORD 'newpassword123';
🔹 Step 2: Create the database
CREATE DATABASE pharma_pos;
🔹 Step 3: Give access
GRANT ALL PRIVILEGES ON DATABASE pharma_pos TO pharma_user;
🔹 (Optional but recommended)

Make the user owner of the DB:

ALTER DATABASE pharma_pos OWNER TO pharma_user;
🔹 Step 4: Exit
\q