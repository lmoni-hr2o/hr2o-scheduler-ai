const admin = require("firebase-admin");

exports.importData = async (req, res) => {
    const db = admin.firestore();
    const { company_id, employees } = req.body;

    if (!company_id || !Array.isArray(employees)) {
        return res.status(400).json({ error: "Invalid payload format. 'company_id' and 'employees' array required." });
    }

    try {
        const batch = db.batch();
        const companyRef = db.collection("companies").doc(company_id);

        // Ensure company exists (upsert)
        batch.set(companyRef, { updated_at: admin.firestore.FieldValue.serverTimestamp() }, { merge: true });

        // Process employees
        employees.forEach((emp) => {
            // Use external ID or generate one
            const empId = emp.id || db.collection("companies").doc(company_id).collection("employees").doc().id;
            const empRef = companyRef.collection("employees").doc(empId);

            // Clean payload
            const data = {
                first_name: emp.first_name,
                last_name: emp.last_name,
                role: emp.role,
                contract: emp.contract || {},
                updated_at: admin.firestore.FieldValue.serverTimestamp(),
                // Initialize preferences if new, otherwise merge
                // (Here just setting user provided data, usually preferences are internal)
            };

            batch.set(empRef, data, { merge: true });
        });

        await batch.commit();

        return res.status(200).json({
            message: "Import successful",
            count: employees.length
        });

    } catch (error) {
        console.error("Import Error:", error);
        return res.status(500).json({ error: "Failed to write to database" });
    }
};
