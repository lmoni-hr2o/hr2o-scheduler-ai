const crypto = require("crypto");

// In production, use Google Secret Manager. 
// For this prototype, we'll try to read from env or fallback to a dev key.
const API_SECRET_KEY = process.env.API_SECRET_KEY || "development-secret-key-12345";

exports.validateHmac = (req, res, next) => {
    const signature = req.headers["x-signature"];

    if (!signature) {
        return res.status(401).json({ error: "Missing X-Signature header" });
    }

    try {
        // We must use the raw body for HMAC verification if possible, 
        // but in Cloud Functions/Express, req.body is already parsed JSON.
        // For simplicity here, we re-stringify, but strictly speaking, 
        // we should use a raw body buffer for exact matching. 
        // A robust production implementation uses 'verify' option in body-parser.

        // Simplification for prototype: strictly expect JSON
        const payloadInfo = JSON.stringify(req.body);

        // Compute HMAC
        const hmac = crypto.createHmac("sha256", API_SECRET_KEY);
        hmac.update(payloadInfo);
        const calculatedSignature = hmac.digest("hex");

        // Constant-time comparison to prevent timing attacks
        const isValid = crypto.timingSafeEqual(
            Buffer.from(signature),
            Buffer.from(calculatedSignature)
        );

        if (!isValid) {
            console.error(`Invalid Signature. Expected: ${calculatedSignature}, Got: ${signature}`);
            return res.status(403).json({ error: "Invalid Signature" });
        }

        next();
    } catch (error) {
        console.error("HMAC Validation Error:", error);
        return res.status(500).json({ error: "Authentication failed internally" });
    }
};
