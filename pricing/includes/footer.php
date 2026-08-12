<?php
/**
 * includes/footer.php — Shared Footer and Script imports
 * 
 * Biến có thể set trước khi include:
 *   $extraScripts (string) — Các thẻ <script> hoặc mã script đặc thù của trang
 */
$extraScripts = $extraScripts ?? '';
?>
    </div> <!-- Close app-container -->

    <!-- Shared Scripts -->
    <script src="assets/config.js"></script>
    <script src="assets/loader.js"></script>
    <script src="assets/pagination.js"></script>

    <!-- Page Specific Scripts -->
    <?= $extraScripts ?>
</body>
</html>
