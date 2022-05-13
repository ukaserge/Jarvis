import {BrowserModule} from "@angular/platform-browser";
import {NgModule} from '@angular/core';
import {AlarmsComponent} from "./alarms.component";
import {TimepickerModule} from "ngx-bootstrap/timepicker";
import {FormsModule} from "@angular/forms";
import {RouterModule} from "@angular/router";
import {MatIconModule} from "@angular/material/icon";
import {LoadingModule} from "../../shared/loading/loading.module";

@NgModule({
  declarations: [
    AlarmsComponent
  ],
  imports: [
    BrowserModule,
    FormsModule,
    RouterModule,
    MatIconModule,
    TimepickerModule,
    LoadingModule,
  ],
  providers: [],
  bootstrap: [],
  exports: [AlarmsComponent]
})
export class AlarmsModule {
}
