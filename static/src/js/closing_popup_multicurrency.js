/** @odoo-module **/

import { ClosePosPopup } from "@point_of_sale/app/navbar/closing_popup/closing_popup";

// Keep the native component untouched except for accepting the backend payload.
// The XML consumes pre-formatted strings directly, so it does not depend on
// prototype helper methods and cannot fail with ctx.<helper> is not a function.
if (!ClosePosPopup.props.includes("multicurrency_summary")) {
    ClosePosPopup.props = [...ClosePosPopup.props, "multicurrency_summary"];
}
