// Auto-submit filter when dropdown changes
(function($) {
    'use strict';
    
    $(document).ready(function() {
        console.log('Admin filter script loaded');
        
        // Event delegation for Select2 dropdowns
        $(document).on('select2:select', 'select', function(e) {
            var selectElement = this;
            var paramName = selectElement.name || selectElement.id;
            
            // Skip action dropdown
            if (!paramName || paramName === 'action') return;
            
            var selectedValue = e.params.data.id;
            var selectedText = e.params.data.text;
            
            console.log('Select2 Filter:', paramName, 'Value:', selectedValue, 'Text:', selectedText);
            
            // If empty or separator - remove filter and show all
            if (!selectedValue || selectedValue === '' || selectedValue === '---------' || selectedText === '---------') {
                var url = new URL(window.location.href);
                url.searchParams.delete(paramName);
                window.location.href = url.toString();
                return;
            }
            
            // Apply filter
            var url = new URL(window.location.href);
            url.searchParams.set(paramName, selectedValue);
            window.location.href = url.toString();
        });
    });
})(jQuery);
